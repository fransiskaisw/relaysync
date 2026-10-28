"""Tipe data bersama lapisan domain."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .geometry import Vec3
from .states import AlertReason, State


class Role(str, Enum):
    EDGE1 = "edge1"  # pelari 1, pembawa tongkat
    EDGE2 = "edge2"  # pelari 2, penerima tongkat


class Readiness(str, Enum):
    STATIONARY = "STATIONARY"
    ARMING = "ARMING"
    RUNNING = "RUNNING"


class StepsSource(str, Enum):
    HW = "hw"
    ACCEL = "accel"


@dataclass(frozen=True, slots=True)
class AccelSample:
    t_s: float
    xyz: Vec3  # m/s^2


@dataclass(frozen=True, slots=True)
class GyroSample:
    t_s: float
    xyz: Vec3  # rad/s


@dataclass(frozen=True, slots=True)
class SensorBatch:
    """Sampel mentah satu jendela. Tidak pernah dikirim ke jaringan."""

    duration_s: float
    accel: tuple[AccelSample, ...]
    gyro: tuple[GyroSample, ...]
    step_counter: int | None  # nilai kumulatif terbaru sejak boot, None bila tak ada kabar


@dataclass(frozen=True, slots=True)
class WindowFeatures:
    window_s: float
    steps_total: int
    dist_est_m: float
    step_len_m: float
    cadence_spm: float
    accel_dev_rms: float
    steps_src: StepsSource
    calibrated: bool
    gyro_path_rad: float | None = None  # hanya edge2
    readiness: Readiness | None = None  # hanya edge2


@dataclass(frozen=True, slots=True)
class Telemetry:
    dev: Role
    run: str
    n_msg: int
    t_ms: int
    features: WindowFeatures


class AlertKind(str, Enum):
    ALERT = "alert"
    CLEARED = "cleared"


@dataclass(frozen=True, slots=True)
class AlertMessage:
    event: AlertKind
    reason: AlertReason
    gap_m: float
    issued_ms: int


@dataclass(frozen=True, slots=True)
class CueMessage:
    issued_ms: int


class EventKind(str, Enum):
    SESSION = "session"
    STATE = "state"
    ALERT = "alert"
    CUE = "cue"
    HANDOFF = "handoff"
    ATTEMPT = "attempt"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    kind: EventKind
    at_ms: int
    message: str
    data: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    attempt_no: int
    gap_m: float
    v1_mps: float
    v2_mps: float
    cue_to_handoff_s: float | None
    alerts: tuple[str, ...]
    score: int
    kind: str  # "manual" atau "auto"


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    state: State
    reason: str
    active: bool
    x1_m: float
    x2_m: float
    gap_m: float
    remaining_to_zone_m: float
    v1_mps: float
    v2_mps: float
    cadence1_spm: float
    cadence2_spm: float
    readiness2: Readiness | None
    eta_s: float | None
    alert_active: bool
    alert_reason: AlertReason | None
    attempt_no: int
    quality_score: int | None
    nodes_online: Mapping[str, bool]
    leg_length_m: float
    zone_length_m: float
    at_ms: int
