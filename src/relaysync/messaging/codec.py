"""Pengkodean dan validasi ketat payload JSON RelaySync (skema v1)."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from relaysync.domain.models import (
    AlertKind,
    AlertMessage,
    CueMessage,
    EngineEvent,
    EventKind,
    Readiness,
    Role,
    SessionSnapshot,
    StepsSource,
    Telemetry,
    WindowFeatures,
)
from relaysync.domain.states import AlertReason, State
from relaysync.settings.models import Settings

from .errors import CommandRejected, PayloadError, TelemetryRejected

SCHEMA_VERSION = 1
MAX_TEXT_LEN = 240
MAX_RUN_LEN = 16
MAX_WINDOW_S = 10.0
MIN_WINDOW_S = 0.01
MAX_STEPS = 10_000_000
MAX_DIST_M = 100_000.0
MIN_STEP_LEN_M = 0.1
MAX_STEP_LEN_M = 5.0
MAX_CADENCE_SPM = 400.0
MAX_ACCEL_DEV = 200.0
MAX_GYRO_PATH = 1_000.0
MAX_EPOCH_MS = 4_102_444_800_000  # tahun 2100
MAX_SPEED_MPS = 50.0
MAX_POS_M = 1_000_000.0
MAX_ETA_S = 100_000.0
MAX_ATTEMPT = 1_000_000

_MISSING = object()
_BASE_KEYS = frozenset({
    "v", "dev", "run", "n_msg", "t_ms", "window_s", "steps_total", "dist_est_m",
    "step_len_m", "cadence_spm", "accel_dev_rms", "steps_src", "calibrated",
})
_EDGE2_KEYS = _BASE_KEYS | {"gyro_path_rad", "readiness"}


# ---------------------------------------------------------------- helpers
def _dumps(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _loads(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PayloadError(f"bukan JSON yang valid: {exc}") from exc
    if not isinstance(data, dict):
        raise PayloadError("payload harus berupa objek JSON")
    return data


def _field(data: Mapping[str, Any], key: str) -> Any:
    value = data.get(key, _MISSING)
    if value is _MISSING:
        raise PayloadError(f"field '{key}' tidak ada")
    return value


def _number(data: Mapping[str, Any], key: str, lo: float, hi: float, *, nullable: bool = False) -> Any:
    value = _field(data, key)
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PayloadError(f"field '{key}' harus angka")
    number = float(value)
    if not math.isfinite(number) or not lo <= number <= hi:
        raise PayloadError(f"field '{key}' di luar rentang [{lo}, {hi}]")
    return number


def _integer(data: Mapping[str, Any], key: str, lo: int, hi: int, *, nullable: bool = False) -> Any:
    value = _field(data, key)
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise PayloadError(f"field '{key}' harus bilangan bulat dalam [{lo}, {hi}]")
    return value


def _text(data: Mapping[str, Any], key: str, max_len: int = MAX_TEXT_LEN) -> str:
    value = _field(data, key)
    if not isinstance(value, str) or not value or len(value) > max_len:
        raise PayloadError(f"field '{key}' harus teks 1 sampai {max_len} karakter")
    return value


def _flag(data: Mapping[str, Any], key: str) -> bool:
    value = _field(data, key)
    if not isinstance(value, bool):
        raise PayloadError(f"field '{key}' harus true atau false")
    return value


def _choice(data: Mapping[str, Any], key: str, enum_type: type[Enum], *, nullable: bool = False) -> Any:
    value = _field(data, key)
    if value is None and nullable:
        return None
    try:
        return enum_type(value)
    except ValueError as exc:
        raise PayloadError(f"field '{key}' bernilai tidak dikenal") from exc


def _exact_keys(data: Mapping[str, Any], expected: frozenset[str]) -> None:
    if set(data) != expected:
        raise PayloadError(f"kunci tidak sesuai skema: {sorted(set(data) ^ expected)}")


def _version(data: Mapping[str, Any]) -> None:
    if data.get("v") != SCHEMA_VERSION:
        raise PayloadError(f"versi skema harus {SCHEMA_VERSION}")


# -------------------------------------------------------------- telemetry
def encode_telemetry(t: Telemetry) -> bytes:
    f = t.features
    body: dict[str, Any] = {
        "v": SCHEMA_VERSION, "dev": t.dev.value, "run": t.run, "n_msg": t.n_msg, "t_ms": t.t_ms,
        "window_s": round(f.window_s, 3), "steps_total": f.steps_total,
        "dist_est_m": round(f.dist_est_m, 2), "step_len_m": round(f.step_len_m, 3),
        "cadence_spm": round(f.cadence_spm, 1), "accel_dev_rms": round(f.accel_dev_rms, 3),
        "steps_src": f.steps_src.value, "calibrated": f.calibrated,
    }
    if t.dev is Role.EDGE2:
        body["gyro_path_rad"] = round(f.gyro_path_rad or 0.0, 3)
        body["readiness"] = (f.readiness or Readiness.STATIONARY).value
    return _dumps(body)


def _features(data: Mapping[str, Any], role: Role) -> WindowFeatures:
    edge2 = role is Role.EDGE2
    return WindowFeatures(
        window_s=_number(data, "window_s", MIN_WINDOW_S, MAX_WINDOW_S),
        steps_total=_integer(data, "steps_total", 0, MAX_STEPS),
        dist_est_m=_number(data, "dist_est_m", 0.0, MAX_DIST_M),
        step_len_m=_number(data, "step_len_m", MIN_STEP_LEN_M, MAX_STEP_LEN_M),
        cadence_spm=_number(data, "cadence_spm", 0.0, MAX_CADENCE_SPM),
        accel_dev_rms=_number(data, "accel_dev_rms", 0.0, MAX_ACCEL_DEV),
        steps_src=_choice(data, "steps_src", StepsSource),
        calibrated=_flag(data, "calibrated"),
        gyro_path_rad=_number(data, "gyro_path_rad", 0.0, MAX_GYRO_PATH) if edge2 else None,
        readiness=_choice(data, "readiness", Readiness) if edge2 else None,
    )


def _decode_telemetry(expected: Role, raw: bytes, now_ms: int, max_skew_s: float | None) -> Telemetry:
    data = _loads(raw)
    _exact_keys(data, _EDGE2_KEYS if expected is Role.EDGE2 else _BASE_KEYS)
    _version(data)
    if _text(data, "dev", 8) != expected.value:
        raise PayloadError("dev tidak cocok dengan topic")
    t_ms = _integer(data, "t_ms", 1, MAX_EPOCH_MS)
    if max_skew_s is not None and abs(now_ms - t_ms) > max_skew_s * 1000:
        raise PayloadError("t_ms terlalu jauh dari waktu engine (pesan basi atau jam salah)")
    return Telemetry(expected, _text(data, "run", MAX_RUN_LEN), _integer(data, "n_msg", 0, 2**31),
                     t_ms, _features(data, expected))


def decode_telemetry(expected: Role, raw: bytes, *, now_ms: int, max_skew_s: float | None) -> Telemetry:
    """Validasi ketat. `max_skew_s=None` menonaktifkan cek jam (untuk replay)."""
    try:
        return _decode_telemetry(expected, raw, now_ms, max_skew_s)
    except PayloadError as exc:
        raise TelemetryRejected(str(exc)) from exc


class SequenceGuard:
    """Menolak n_msg yang tidak naik pada run yang sama (duplikat atau mundur)."""

    def __init__(self) -> None:
        self._last: dict[tuple[Role, str], int] = {}

    def check(self, t: Telemetry) -> None:
        key = (t.dev, t.run)
        last = self._last.get(key)
        if last is not None and t.n_msg <= last:
            raise TelemetryRejected(f"n_msg {t.n_msg} tidak naik (terakhir {last})")
        self._last[key] = t.n_msg


# ---------------------------------------------------------------- session
def encode_session(s: SessionSnapshot) -> bytes:
    return _dumps({
        "v": SCHEMA_VERSION, "state": s.state.value, "reason": s.reason, "active": s.active,
        "x1_m": round(s.x1_m, 2), "x2_m": round(s.x2_m, 2), "gap_m": round(s.gap_m, 2),
        "remaining_to_zone_m": round(s.remaining_to_zone_m, 2),
        "v1_mps": round(s.v1_mps, 2), "v2_mps": round(s.v2_mps, 2),
        "cadence1_spm": round(s.cadence1_spm, 1), "cadence2_spm": round(s.cadence2_spm, 1),
        "readiness2": s.readiness2.value if s.readiness2 else None,
        "eta_s": None if s.eta_s is None else round(s.eta_s, 2),
        "alert_active": s.alert_active,
        "alert_reason": s.alert_reason.value if s.alert_reason else None,
        "attempt_no": s.attempt_no, "quality_score": s.quality_score,
        "nodes_online": dict(s.nodes_online), "leg_length_m": s.leg_length_m,
        "zone_length_m": s.zone_length_m, "at_ms": s.at_ms,
    })


def decode_session(raw: bytes) -> SessionSnapshot:
    data = _loads(raw)
    _version(data)
    nodes = _field(data, "nodes_online")
    if not isinstance(nodes, dict) or not all(
        isinstance(k, str) and isinstance(v, bool) for k, v in nodes.items()
    ):
        raise PayloadError("nodes_online harus objek nama ke boolean")
    pos = MAX_POS_M
    return SessionSnapshot(
        state=_choice(data, "state", State), reason=_text(data, "reason"),
        active=_flag(data, "active"),
        x1_m=_number(data, "x1_m", -pos, pos), x2_m=_number(data, "x2_m", -pos, pos),
        gap_m=_number(data, "gap_m", -pos, pos),
        remaining_to_zone_m=_number(data, "remaining_to_zone_m", -pos, pos),
        v1_mps=_number(data, "v1_mps", -MAX_SPEED_MPS, MAX_SPEED_MPS),
        v2_mps=_number(data, "v2_mps", -MAX_SPEED_MPS, MAX_SPEED_MPS),
        cadence1_spm=_number(data, "cadence1_spm", 0.0, MAX_CADENCE_SPM),
        cadence2_spm=_number(data, "cadence2_spm", 0.0, MAX_CADENCE_SPM),
        readiness2=_choice(data, "readiness2", Readiness, nullable=True),
        eta_s=_number(data, "eta_s", 0.0, MAX_ETA_S, nullable=True),
        alert_active=_flag(data, "alert_active"),
        alert_reason=_choice(data, "alert_reason", AlertReason, nullable=True),
        attempt_no=_integer(data, "attempt_no", 1, MAX_ATTEMPT),
        quality_score=_integer(data, "quality_score", 0, 100, nullable=True),
        nodes_online=dict(nodes), leg_length_m=_number(data, "leg_length_m", 0.0, pos),
        zone_length_m=_number(data, "zone_length_m", 0.0, pos),
        at_ms=_integer(data, "at_ms", 0, MAX_EPOCH_MS),
    )


# ------------------------------------------------------------ alert, cue
def encode_alert(m: AlertMessage) -> bytes:
    return _dumps({"event": m.event.value, "reason": m.reason.value,
                   "gap_m": round(m.gap_m, 2), "issued_ms": m.issued_ms})


def decode_alert(raw: bytes) -> AlertMessage:
    data = _loads(raw)
    return AlertMessage(
        event=_choice(data, "event", AlertKind), reason=_choice(data, "reason", AlertReason),
        gap_m=_number(data, "gap_m", -MAX_POS_M, MAX_POS_M),
        issued_ms=_integer(data, "issued_ms", 0, MAX_EPOCH_MS),
    )


def encode_cue(m: CueMessage) -> bytes:
    return _dumps({"cue": "go", "issued_ms": m.issued_ms})


def decode_cue(raw: bytes) -> CueMessage:
    data = _loads(raw)
    if data.get("cue") != "go":
        raise PayloadError("jenis cue tidak dikenal")
    return CueMessage(_integer(data, "issued_ms", 0, MAX_EPOCH_MS))


# ------------------------------------------------------------------ event
def encode_event(e: EngineEvent) -> bytes:
    return _dumps({"v": SCHEMA_VERSION, "kind": e.kind.value, "at_ms": e.at_ms,
                   "message": e.message, "data": dict(e.data)})


def decode_event(raw: bytes) -> EngineEvent:
    data = _loads(raw)
    extra = _field(data, "data")
    if not isinstance(extra, dict):
        raise PayloadError("field 'data' harus objek")
    return EngineEvent(_choice(data, "kind", EventKind), _integer(data, "at_ms", 0, MAX_EPOCH_MS),
                       _text(data, "message"), extra)


# ---------------------------------------------------------------- control
class CommandName(str, Enum):
    START = "start"
    STOP = "stop"
    RESET = "reset"
    ACK = "ack"
    HANDOFF = "handoff"
    CALIBRATE_STEP = "calibrate_step"
    CONFIG = "config"
    NEW_ATTEMPT = "new_attempt"


@dataclass(frozen=True, slots=True)
class ControlCommand:
    name: CommandName
    target: Role | None = None
    distance_m: float | None = None
    leg_length_m: float | None = None
    zone_length_m: float | None = None


@dataclass(frozen=True, slots=True)
class CommandLimits:
    calibrate_default_m: float
    calibrate_min_m: float
    calibrate_max_m: float
    leg_min_m: float
    leg_max_m: float
    zone_min_m: float
    zone_max_m: float


def limits_from_settings(settings: Settings) -> CommandLimits:
    e = settings.engine
    return CommandLimits(e.calibrate_default_m, e.calibrate_min_m, e.calibrate_max_m,
                         e.leg_min_m, e.leg_max_m, e.zone_min_m, e.zone_max_m)


def encode_command(cmd: ControlCommand) -> bytes:
    body: dict[str, Any] = {"cmd": cmd.name.value}
    if cmd.target is not None:
        body["target"] = cmd.target.value
    for key, value in (("distance_m", cmd.distance_m), ("leg_length_m", cmd.leg_length_m),
                       ("zone_length_m", cmd.zone_length_m)):
        if value is not None:
            body[key] = value
    return _dumps(body)


# nama perintah -> (kunci wajib, kunci opsional)
_PARAMS: dict[CommandName, tuple[frozenset[str], frozenset[str]]] = {
    CommandName.START: (frozenset(), frozenset()),
    CommandName.STOP: (frozenset(), frozenset()),
    CommandName.RESET: (frozenset(), frozenset()),
    CommandName.ACK: (frozenset(), frozenset()),
    CommandName.HANDOFF: (frozenset(), frozenset()),
    CommandName.NEW_ATTEMPT: (frozenset(), frozenset()),
    CommandName.CALIBRATE_STEP: (frozenset({"target"}), frozenset({"distance_m"})),
    CommandName.CONFIG: (frozenset(), frozenset({"leg_length_m", "zone_length_m"})),
}


def _decode_command(raw: bytes, limits: CommandLimits) -> ControlCommand:
    data = _loads(raw)
    name = _choice(data, "cmd", CommandName)
    required, optional = _PARAMS[name]
    keys = set(data) - {"cmd"}
    if not required <= keys or not keys <= required | optional:
        raise PayloadError(f"parameter perintah tidak sesuai: {sorted(keys)}")
    if name is CommandName.CALIBRATE_STEP:
        distance = limits.calibrate_default_m
        if "distance_m" in data:
            distance = _number(data, "distance_m", limits.calibrate_min_m, limits.calibrate_max_m)
        return ControlCommand(name, target=_choice(data, "target", Role), distance_m=distance)
    if name is CommandName.CONFIG:
        if not keys:
            raise PayloadError("config membutuhkan leg_length_m atau zone_length_m")
        leg = _number(data, "leg_length_m", limits.leg_min_m, limits.leg_max_m) if "leg_length_m" in data else None
        zone = _number(data, "zone_length_m", limits.zone_min_m, limits.zone_max_m) if "zone_length_m" in data else None
        return ControlCommand(name, leg_length_m=leg, zone_length_m=zone)
    return ControlCommand(name)


def decode_command(raw: bytes, limits: CommandLimits) -> ControlCommand:
    try:
        return _decode_command(raw, limits)
    except PayloadError as exc:
        raise CommandRejected(str(exc)) from exc
