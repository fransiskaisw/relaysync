"""Penyimpanan thread-safe dan langganan MQTT untuk dashboard Streamlit."""
from __future__ import annotations

import logging
import secrets
import threading
from collections import deque
from dataclasses import dataclass

from relaysync.adapters.memory_bus import MemoryBroker, MemoryBus
from relaysync.adapters.mqtt_bus import MqttBus
from relaysync.adapters.system_clock import ManualClock, SystemClock
from relaysync.domain.models import (
    AlertMessage,
    AttemptRecord,
    CueMessage,
    EngineEvent,
    EventKind,
    Role,
    SessionSnapshot,
    Telemetry,
)
from relaysync.messaging import codec
from relaysync.messaging.errors import PayloadError
from relaysync.messaging.recording import (
    Record,
    read_json_records,
    read_telemetry_csv,
)
from relaysync.messaging.topics import KIND_PRESENCE, KIND_TELEMETRY, TopicMap
from relaysync.ports import MessageBus
from relaysync.services.relay_engine import RelayEngine
from relaysync.settings.models import Runtime, Settings

log = logging.getLogger(__name__)

MAX_SERIES = 300
MAX_EVENTS = 200
MAX_ATTEMPTS = 100
PRESENCE_ONLINE = b"online"


@dataclass(frozen=True, slots=True)
class TimePoint:
    t_s: float
    x1_m: float
    x2_m: float
    gap_m: float
    v1_mps: float
    v2_mps: float
    cadence1_spm: float
    cadence2_spm: float


@dataclass(frozen=True, slots=True)
class FeedSnapshot:
    connected: bool
    mode: str
    session: SessionSnapshot | None
    last_telemetry: dict[Role, Telemetry]
    online: dict[Role, bool]
    points: tuple[TimePoint, ...]
    attempts: tuple[AttemptRecord, ...]
    events: tuple[EngineEvent, ...]
    alerts: tuple[AlertMessage, ...]
    cues: tuple[CueMessage, ...]


class DashboardStore:
    """Struktur data terbatas dan thread-safe yang diisi dari MQTT atau replay."""

    def __init__(self, settings: Settings, topics: TopicMap) -> None:
        self._cfg = settings
        self._topics = topics
        self._lock = threading.Lock()
        self._origin_ms: int | None = None
        self._session: SessionSnapshot | None = None
        self._telemetry: dict[Role, Telemetry] = {}
        self._online: dict[Role, bool] = {Role.EDGE1: False, Role.EDGE2: False}
        self._points: deque[TimePoint] = deque(maxlen=MAX_SERIES)
        self._attempts: deque[AttemptRecord] = deque(maxlen=MAX_ATTEMPTS)
        self._events: deque[EngineEvent] = deque(maxlen=MAX_EVENTS)
        self._alerts: deque[AlertMessage] = deque(maxlen=MAX_EVENTS)
        self._cues: deque[CueMessage] = deque(maxlen=MAX_EVENTS)

    def clear(self) -> None:
        with self._lock:
            self._origin_ms = None
            self._session = None
            self._telemetry.clear()
            self._online = {Role.EDGE1: False, Role.EDGE2: False}
            self._points.clear()
            self._attempts.clear()
            self._events.clear()
            self._alerts.clear()
            self._cues.clear()

    def on_message(self, topic: str, payload: bytes) -> None:
        try:
            self._dispatch(topic, payload)
        except PayloadError as exc:
            log.debug("Dashboard mengabaikan pesan di %s: %s", topic, exc)

    def _dispatch(self, topic: str, payload: bytes) -> None:
        t = self._topics
        if topic == t.session:
            snap = codec.decode_session(payload)
            with self._lock:
                self._record_session(snap)
            return
        if topic == t.events:
            ev = codec.decode_event(payload)
            with self._lock:
                self._events.appendleft(ev)
                if ev.kind is EventKind.ATTEMPT:
                    self._record_attempt(ev)
            return
        if topic == t.alerts:
            al = codec.decode_alert(payload)
            with self._lock:
                self._alerts.appendleft(al)
            return
        if topic == t.cues:
            cue = codec.decode_cue(payload)
            with self._lock:
                self._cues.appendleft(cue)
            return
        if topic.startswith(f"{t.root}/edge/"):
            role, kind = t.parse_edge(topic)
            if kind == KIND_PRESENCE:
                with self._lock:
                    self._online[role] = payload.strip() == PRESENCE_ONLINE
            elif kind == KIND_TELEMETRY:
                tele = codec.decode_telemetry(role, payload, now_ms=0, max_skew_s=None)
                with self._lock:
                    self._telemetry[role] = tele

    def _record_session(self, snap: SessionSnapshot) -> None:
        self._session = snap
        for role in Role:
            if role.value in snap.nodes_online:
                self._online[role] = snap.nodes_online[role.value]
        if self._origin_ms is None or snap.at_ms < self._origin_ms:
            self._origin_ms = snap.at_ms
        rel_s = max(0.0, (snap.at_ms - self._origin_ms) / 1000.0)
        self._points.append(
            TimePoint(
                t_s=round(rel_s, 2),
                x1_m=snap.x1_m,
                x2_m=snap.x2_m,
                gap_m=snap.gap_m,
                v1_mps=snap.v1_mps,
                v2_mps=snap.v2_mps,
                cadence1_spm=snap.cadence1_spm,
                cadence2_spm=snap.cadence2_spm,
            )
        )

    def _record_attempt(self, ev: EngineEvent) -> None:
        d = ev.data
        try:
            rec = AttemptRecord(
                attempt_no=int(d["attempt_no"]),
                gap_m=float(d["gap_m"]),
                v1_mps=float(d["v1_mps"]),
                v2_mps=float(d["v2_mps"]),
                cue_to_handoff_s=(
                    None if d.get("cue_to_handoff_s") is None else float(d["cue_to_handoff_s"])
                ),
                alerts=tuple(str(a) for a in d.get("alerts", [])),
                score=int(d["score"]),
                kind=str(d.get("kind", "auto")),
            )
        except (KeyError, TypeError, ValueError):
            return
        self._attempts.append(rec)

    def snapshot(self, *, connected: bool, mode: str) -> FeedSnapshot:
        with self._lock:
            return FeedSnapshot(
                connected=connected,
                mode=mode,
                session=self._session,
                last_telemetry=dict(self._telemetry),
                online=dict(self._online),
                points=tuple(self._points),
                attempts=tuple(self._attempts),
                events=tuple(self._events),
                alerts=tuple(self._alerts),
                cues=tuple(self._cues),
            )


class LiveFeed:
    """Koneksi MQTT latar ditambah pengiriman perintah kontrol."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.topics = TopicMap(runtime.team_id)
        self.store = DashboardStore(runtime.settings, self.topics)
        self._ReplayStore: DashboardStore | None = None
        client_id = f"relaysync-dash-{secrets.token_hex(3)}"
        self._bus = MqttBus(runtime.settings.broker, client_id)
        for topic in self.topics.all_topics():
            self._bus.subscribe(topic, self.store.on_message)
        self._bus.connect(None)
        self._clock = SystemClock()

    @property
    def is_connected(self) -> bool:
        return self._bus.is_connected

    def send_command(self, cmd: codec.ControlCommand) -> None:
        self._bus.publish(self.topics.control, codec.encode_command(cmd), qos=1)

    def load_replay_text(self, filename: str, content: str) -> int:
        """Muat berkas JSONL/JSON atau CSV rekaman ke store replay terpisah."""
        replay_store = DashboardStore(self.runtime.settings, self.topics)
        count = _replay_into_store(
            filename, content, self.runtime.settings, self.topics, replay_store
        )
        self._ReplayStore = replay_store
        return count

    def clear_replay(self) -> None:
        self._ReplayStore = None

    def snapshot(self) -> FeedSnapshot:
        if self._ReplayStore is not None:
            return self._ReplayStore.snapshot(connected=self._bus.is_connected, mode="replay")
        return self.store.snapshot(connected=self._bus.is_connected, mode="live")


def _replay_into_store(
    filename: str,
    content: str,
    settings: Settings,
    topics: TopicMap,
    store: DashboardStore,
) -> int:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return _replay_csv(content, settings, topics, store)
    records = list(read_json_records(content))
    has_session = any(r.topic.endswith("/session") for r in records)
    if has_session:
        for rec in records:
            topic = _normalize_topic(rec.topic, topics)
            store.on_message(topic, rec.payload)
        return len(records)
    return _replay_records_via_engine(records, settings, topics, store)


def _normalize_topic(raw_topic: str, topics: TopicMap) -> str:
    parts = raw_topic.split("/")
    if len(parts) >= 3 and parts[0] == "relaysync":
        suffix = "/".join(parts[2:])
        return f"{topics.root}/{suffix}"
    return raw_topic


def _replay_csv(
    content: str, settings: Settings, topics: TopicMap, store: DashboardStore
) -> int:
    rows = list(read_telemetry_csv(content))
    if not rows:
        return 0
    clock = ManualClock(rows[0][0])
    broker = MemoryBroker()
    eng_bus: MessageBus = MemoryBus(broker)
    dash_bus: MessageBus = MemoryBus(broker)
    for topic in topics.all_topics():
        dash_bus.subscribe(topic, store.on_message)
    dash_bus.connect(None)
    engine = RelayEngine(settings=settings, topics=topics, bus=eng_bus, clock=clock)
    engine.open()
    for role in Role:
        dash_bus.publish(topics.presence(role), PRESENCE_ONLINE, retain=True)
    dash_bus.publish(
        topics.control, codec.encode_command(codec.ControlCommand(codec.CommandName.START))
    )
    last_ms = rows[0][0]
    for received_ms, tele in rows:
        if received_ms > last_ms:
            clock.advance((received_ms - last_ms) / 1000.0)
            last_ms = received_ms
        dash_bus.publish(topics.telemetry(tele.dev), codec.encode_telemetry(tele))
        engine.tick()
    return len(rows)


def _replay_records_via_engine(
    records: list[Record], settings: Settings, topics: TopicMap, store: DashboardStore
) -> int:
    if not records:
        return 0
    clock = ManualClock(records[0].received_ms)
    broker = MemoryBroker()
    eng_bus: MessageBus = MemoryBus(broker)
    dash_bus: MessageBus = MemoryBus(broker)
    for topic in topics.all_topics():
        dash_bus.subscribe(topic, store.on_message)
    dash_bus.connect(None)
    engine = RelayEngine(settings=settings, topics=topics, bus=eng_bus, clock=clock)
    engine.open()
    last_ms = records[0].received_ms
    for rec in records:
        if rec.received_ms > last_ms:
            clock.advance((rec.received_ms - last_ms) / 1000.0)
            last_ms = rec.received_ms
        norm_topic = _normalize_topic(rec.topic, topics)
        dash_bus.publish(norm_topic, rec.payload)
        engine.tick()
    return len(records)
