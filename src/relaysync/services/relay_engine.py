"""Mesin estafet: fusi dua pelari, state machine, cue GO, alert, dan evaluasi percobaan."""
from __future__ import annotations

import logging
import threading
from dataclasses import replace
from typing import Any

from relaysync.domain.cue_policy import Cooldown, CueRules, should_cue_go
from relaysync.domain.fusion import (
    AlertLatch,
    FusionInputs,
    FusionRules,
    HoldTimer,
    ReleaseDelay,
    build_inputs,
    is_optimal,
    raw_alert_reason,
)
from relaysync.domain.geometry import TrackGeometry, eta_to_zone_s
from relaysync.domain.models import (
    AlertKind,
    AlertMessage,
    AttemptRecord,
    CueMessage,
    EngineEvent,
    EventKind,
    Role,
    SessionSnapshot,
    Telemetry,
)
from relaysync.domain.scoring import ScoreRules, transfer_quality
from relaysync.domain.speed import SpeedEstimator
from relaysync.domain.states import (
    ALERT_TEXT,
    STATE_LABELS,
    STATE_REASONS,
    AlertReason,
    State,
    StateFacts,
    transition,
)
from relaysync.messaging import codec
from relaysync.messaging.errors import PayloadError
from relaysync.messaging.topics import KIND_PRESENCE, TopicMap
from relaysync.ports import Clock, MessageBus
from relaysync.settings.models import Settings

log = logging.getLogger(__name__)

MS_PER_S = 1000.0
PRESENCE_ONLINE = b"online"


class _Attempt:
    """Keadaan mutable satu percobaan serah terima."""

    def __init__(self) -> None:
        self.handed_off = False
        self.alerts: list[str] = []
        self.cue_s: float | None = None
        self.score: int | None = None


class RelayEngine:
    def __init__(self, *, settings: Settings, topics: TopicMap, bus: MessageBus, clock: Clock) -> None:
        self._cfg = settings
        self._topics, self._bus, self._clock = topics, bus, clock
        self._lock = threading.RLock()
        self._guard = codec.SequenceGuard()
        self._limits = codec.limits_from_settings(settings)
        t, f, c, s = settings.track, settings.fusion, settings.cue, settings.score
        self._geometry = TrackGeometry(t.leg_length_m, t.zone_length_m, t.entry_margin_m)
        self._fusion = FusionRules(f.gap_opt_min_m, f.gap_opt_max_m, f.gap_far_m,
                                   f.speed_match_tol_mps, f.early_start_margin_m, f.stall_cadence_spm)
        self._cue_rules = CueRules(c.go_trigger_m, c.go_cue_eta_s)
        self._score_rules = ScoreRules(s.start, s.gap_target_m, s.gap_penalty_per_m,
                                       s.speed_penalty_per_mps, s.alert_penalty, s.clean_bonus)
        hold = {reason: f.hold_s for reason in AlertReason}
        hold[AlertReason.RUNNER1_STALLED] = f.stall_s  # punya durasi sendiri
        self._latch = AlertLatch(hold, f.clear_s)
        self._optimal_gate = ReleaseDelay(f.optimal_exit_s)
        self._pass_timer = HoldTimer(f.pass_hold_s)
        self._cue_cd = Cooldown(c.cue_cooldown_s)
        self._alert_cd = Cooldown(c.alert_cooldown_s)
        self._seen: dict[Role, tuple[int, Telemetry]] = {}
        self._speed = {role: SpeedEstimator(settings.speed.window_s) for role in Role}
        self._online = {role: False for role in Role}
        self._active = False
        self._attempt_no = 1
        self._attempt = _Attempt()
        self._announced: AlertReason | None = None
        self._state = State.IDLE
        self._last_publish_ms = 0

    # ------------------------------------------------------------ lifecycle
    def open(self) -> None:
        t = self._topics
        for role in Role:
            self._bus.subscribe(t.telemetry(role), self._on_edge_message)
            self._bus.subscribe(t.presence(role), self._on_edge_message)
        self._bus.subscribe(t.control, self._on_control)
        self._bus.connect(None)
        with self._lock:
            self._publish_session(self._clock.now_ms(), force=True)

    def run(self, stop: threading.Event) -> None:
        self.open()
        try:
            while not stop.is_set():
                self._clock.sleep(self._cfg.engine.tick_s)
                self.tick()
        finally:
            self._bus.disconnect()

    def tick(self) -> None:
        with self._lock:
            self._refresh(self._clock.now_ms())

    # ------------------------------------------------------------- handlers
    def _on_edge_message(self, topic: str, payload: bytes) -> None:
        now = self._clock.now_ms()
        try:
            role, kind = self._topics.parse_edge(topic)
            if kind == KIND_PRESENCE:
                with self._lock:
                    self._online[role] = payload.strip() == PRESENCE_ONLINE
                    self._publish_session(now, force=True)
                return
            telemetry = codec.decode_telemetry(
                role, payload, now_ms=now, max_skew_s=self._cfg.engine.max_clock_skew_s)
            self._guard.check(telemetry)
        except PayloadError as exc:
            log.warning("Pesan ditolak (%s): %s", topic, exc)
            return
        with self._lock:
            self._seen[role] = (now, telemetry)
            self._speed[role].record(now / MS_PER_S, telemetry.features.dist_est_m)
            self._refresh(now)

    def _on_control(self, _topic: str, payload: bytes) -> None:
        try:
            command = codec.decode_command(payload, self._limits)
        except PayloadError as exc:
            log.warning("Perintah ditolak: %s", exc)
            return
        now = self._clock.now_ms()
        with self._lock:
            actions = {
                codec.CommandName.START: self._cmd_start, codec.CommandName.STOP: self._cmd_stop,
                codec.CommandName.RESET: self._cmd_reset, codec.CommandName.ACK: self._cmd_ack,
                codec.CommandName.HANDOFF: self._cmd_handoff,
                codec.CommandName.CALIBRATE_STEP: self._cmd_calibrate,
                codec.CommandName.CONFIG: self._cmd_config,
                codec.CommandName.NEW_ATTEMPT: self._cmd_new_attempt,
            }
            actions[command.name](command, now)
            self._refresh(now, force=True)

    # ------------------------------------------------------------- commands
    def _begin_attempt(self, now: int) -> None:
        """Bersihkan semua keadaan per percobaan; edge ikut rebase lewat topic control."""
        self._clear_announced(now)
        self._attempt = _Attempt()
        self._latch.reset()
        for gate in (self._optimal_gate, self._pass_timer, self._cue_cd, self._alert_cd):
            gate.reset()
        self._seen.clear()
        for estimator in self._speed.values():
            estimator.clear()

    def _cmd_start(self, _cmd: codec.ControlCommand, now: int) -> None:
        if self._attempt.handed_off:
            self._attempt_no += 1
        self._begin_attempt(now)
        self._active = True
        self._emit(EventKind.SESSION, f"Percobaan {self._attempt_no} dimulai.", now)

    def _cmd_new_attempt(self, _cmd: codec.ControlCommand, now: int) -> None:
        self._attempt_no += 1
        self._begin_attempt(now)
        self._active = True
        self._emit(EventKind.SESSION, f"Percobaan {self._attempt_no} dimulai.", now)

    def _cmd_stop(self, _cmd: codec.ControlCommand, now: int) -> None:
        self._clear_announced(now)
        self._active = False
        self._emit(EventKind.SESSION, "Sesi dihentikan.", now)

    def _cmd_reset(self, _cmd: codec.ControlCommand, now: int) -> None:
        self._begin_attempt(now)
        self._active = False
        self._attempt_no = 1
        self._emit(EventKind.SESSION, "Sesi di-reset.", now)

    def _cmd_ack(self, _cmd: codec.ControlCommand, now: int) -> None:
        self._latch.ack()
        self._clear_announced(now)
        self._emit(EventKind.CONTROL, "Alert diakui.", now)

    def _cmd_handoff(self, _cmd: codec.ControlCommand, now: int) -> None:
        inputs = self._inputs()
        if not self._active or self._attempt.handed_off or inputs is None:
            log.warning("Serah terima manual diabaikan (sesi tidak aktif atau data belum lengkap).")
            return
        self._complete_handoff("manual", inputs, now)

    def _cmd_calibrate(self, cmd: codec.ControlCommand, now: int) -> None:
        target = cmd.target.value if cmd.target else "?"
        self._emit(EventKind.CONTROL, f"Kalibrasi langkah {target} diminta.", now,
                   {"distance_m": cmd.distance_m})

    def _cmd_config(self, cmd: codec.ControlCommand, now: int) -> None:
        g = self._geometry
        self._geometry = replace(
            g, leg_length_m=cmd.leg_length_m or g.leg_length_m,
            zone_length_m=cmd.zone_length_m or g.zone_length_m)
        self._emit(EventKind.CONTROL,
                   f"Lintasan: pelari 2 menunggu di {self._geometry.leg_length_m:g} m, "
                   f"zona {self._geometry.zone_length_m:g} m.", now)

    # ------------------------------------------------------------ evaluation
    def _inputs(self) -> FusionInputs | None:
        if len(self._seen) < len(Role):
            return None
        f1 = self._seen[Role.EDGE1][1].features
        f2 = self._seen[Role.EDGE2][1].features
        return build_inputs(
            self._geometry, f1.dist_est_m, f2.dist_est_m, self._speed[Role.EDGE1].speed_mps(),
            self._speed[Role.EDGE2].speed_mps(), f1.cadence_spm, f2.readiness)

    def _is_stale(self, now: int) -> bool:
        limit = self._cfg.fusion.data_gap_s * MS_PER_S
        return any(now - received > limit for received, _ in self._seen.values())

    def _refresh(self, now: int, force: bool = False) -> None:
        now_s = now / MS_PER_S
        inputs = self._inputs()
        stale = self._is_stale(now)
        optimal = False
        if self._active and inputs is not None and not stale and not self._attempt.handed_off:
            optimal = self._evaluate(inputs, now, now_s)
        facts = StateFacts(self._active, inputs is not None, stale, self._attempt.handed_off,
                           self._latch.active is not None, optimal)
        new_state = transition(facts)
        changed = new_state is not self._state
        if changed:
            self._set_state(new_state, now)
        self._publish_session(now, force=force or changed)

    def _evaluate(self, inputs: FusionInputs, now: int, now_s: float) -> bool:
        reason = self._latch.update(raw_alert_reason(inputs, self._geometry, self._fusion), now_s)
        self._dispatch_alert(reason, inputs.gap_m, now, now_s)
        optimal = self._optimal_gate.update(is_optimal(inputs, self._geometry, self._fusion), now_s)
        self._maybe_cue(inputs, now, now_s)
        passing = optimal and inputs.gap_m < self._cfg.fusion.pass_gap_m
        if self._pass_timer.update(passing, now_s) and self._cfg.fusion.auto_handoff:
            self._complete_handoff("auto", inputs, now)
        return optimal

    def _maybe_cue(self, inputs: FusionInputs, now: int, now_s: float) -> None:
        eta = eta_to_zone_s(inputs.remaining_m, inputs.v1_mps, self._cfg.speed.min_speed_mps)
        if not should_cue_go(inputs.remaining_m, eta, inputs.readiness2, self._cue_rules):
            return
        if not self._cue_cd.ready(now_s):
            return
        self._cue_cd.mark(now_s)
        if self._attempt.cue_s is None:
            self._attempt.cue_s = now_s
        self._bus.publish(self._topics.cues, codec.encode_cue(CueMessage(now)), qos=1)
        self._emit(EventKind.CUE, "Cue GO dikirim ke pelari 2.", now,
                   {"remaining_to_zone_m": round(inputs.remaining_m, 1)})

    def _dispatch_alert(self, reason: AlertReason | None, gap_m: float, now: int,
                        now_s: float) -> None:
        if reason is None:
            self._clear_announced(now, gap_m)
            return
        if reason is self._announced and not self._alert_cd.ready(now_s):
            return
        if reason is not self._announced:
            self._attempt.alerts.append(reason.value)
            self._emit(EventKind.ALERT, ALERT_TEXT[reason], now, {"reason": reason.value})
        self._announced = reason
        self._alert_cd.mark(now_s)
        self._bus.publish(self._topics.alerts, codec.encode_alert(
            AlertMessage(AlertKind.ALERT, reason, gap_m, now)), qos=1)

    def _clear_announced(self, now: int, gap_m: float = 0.0) -> None:
        if self._announced is None:
            return
        self._bus.publish(self._topics.alerts, codec.encode_alert(
            AlertMessage(AlertKind.CLEARED, self._announced, gap_m, now)), qos=1)
        self._emit(EventKind.ALERT, "Alert padam.", now, {"reason": self._announced.value})
        self._announced = None
        self._alert_cd.reset()

    def _complete_handoff(self, kind: str, inputs: FusionInputs, now: int) -> None:
        a = self._attempt
        score = transfer_quality(inputs.gap_m, inputs.v1_mps, inputs.v2_mps, len(a.alerts),
                                 self._score_rules)
        cue_to_handoff = None if a.cue_s is None else now / MS_PER_S - a.cue_s
        a.handed_off, a.score = True, int(round(score))
        self._latch.reset()
        self._clear_announced(now, inputs.gap_m)
        record = AttemptRecord(self._attempt_no, inputs.gap_m, inputs.v1_mps, inputs.v2_mps,
                               cue_to_handoff, tuple(a.alerts), a.score, kind)
        self._emit(EventKind.HANDOFF, f"Serah terima ({kind}), skor {a.score}.", now)
        self._emit(EventKind.ATTEMPT, f"Percobaan {self._attempt_no} selesai.", now,
                   _attempt_data(record))

    # ------------------------------------------------------------ publishing
    def _set_state(self, new_state: State, now: int) -> None:
        old, self._state = self._state, new_state
        log.info("Status: %s -> %s", old.value, new_state.value)
        self._emit(EventKind.STATE, f"{STATE_LABELS[old]} -> {STATE_LABELS[new_state]}", now,
                   {"from": old.value, "to": new_state.value})

    def _emit(self, kind: EventKind, text: str, now: int, data: dict[str, Any] | None = None) -> None:
        event = EngineEvent(kind, now, text, data or {})
        self._bus.publish(self._topics.events, codec.encode_event(event), qos=1)

    def _snapshot(self, now: int) -> SessionSnapshot:
        inputs = self._inputs()
        f2 = self._seen[Role.EDGE2][1].features if Role.EDGE2 in self._seen else None
        f1 = self._seen[Role.EDGE1][1].features if Role.EDGE1 in self._seen else None
        reason = self._latch.active
        text = ALERT_TEXT[reason] if reason else STATE_REASONS[self._state]
        eta = None if inputs is None else eta_to_zone_s(
            inputs.remaining_m, inputs.v1_mps, self._cfg.speed.min_speed_mps)
        return SessionSnapshot(
            state=self._state, reason=text, active=self._active,
            x1_m=inputs.x1_m if inputs else 0.0, x2_m=inputs.x2_m if inputs else 0.0,
            gap_m=inputs.gap_m if inputs else 0.0,
            remaining_to_zone_m=inputs.remaining_m if inputs else self._geometry.leg_length_m,
            v1_mps=inputs.v1_mps if inputs else 0.0, v2_mps=inputs.v2_mps if inputs else 0.0,
            cadence1_spm=f1.cadence_spm if f1 else 0.0, cadence2_spm=f2.cadence_spm if f2 else 0.0,
            readiness2=f2.readiness if f2 else None, eta_s=eta,
            alert_active=reason is not None, alert_reason=reason, attempt_no=self._attempt_no,
            quality_score=self._attempt.score,
            nodes_online={role.value: up for role, up in self._online.items()},
            leg_length_m=self._geometry.leg_length_m, zone_length_m=self._geometry.zone_length_m,
            at_ms=now)

    def _publish_session(self, now: int, *, force: bool) -> None:
        heartbeat_ms = self._cfg.engine.session_heartbeat_s * MS_PER_S
        if not force and now - self._last_publish_ms < heartbeat_ms:
            return
        self._last_publish_ms = now
        self._bus.publish(self._topics.session, codec.encode_session(self._snapshot(now)),
                          qos=1, retain=True)


def _attempt_data(r: AttemptRecord) -> dict[str, Any]:
    return {
        "attempt_no": r.attempt_no, "gap_m": round(r.gap_m, 2), "v1_mps": round(r.v1_mps, 2),
        "v2_mps": round(r.v2_mps, 2),
        "cue_to_handoff_s": None if r.cue_to_handoff_s is None else round(r.cue_to_handoff_s, 2),
        "alerts": list(r.alerts), "score": r.score, "kind": r.kind,
    }
