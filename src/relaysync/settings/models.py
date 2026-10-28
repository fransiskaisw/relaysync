"""Model konfigurasi bertipe. Nilai diisi dari configs/default.yaml."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BrokerSettings:
    host: str
    port: int
    tls: bool
    keepalive_s: int
    ws_url: str


@dataclass(frozen=True, slots=True)
class StepLengths:
    edge1_m: float
    edge2_m: float


@dataclass(frozen=True, slots=True)
class EdgeSettings:
    window_s: float
    sample_interval_ms: int
    step_sensor: str
    accel_sensor: str
    gyro_sensor: str
    cadence_window_s: float
    max_gyro_dt_s: float
    step_lengths: StepLengths
    step_len_min_m: float
    step_len_max_m: float
    hw_stall_s: float
    hw_stall_min_accel_steps: int

    @property
    def hw_stall_windows(self) -> int:
        """Jumlah jendela yang diamati untuk mendeteksi step counter yang diam."""
        return max(1, math.ceil(self.hw_stall_s / self.window_s))


@dataclass(frozen=True, slots=True)
class AccelStepSettings:
    threshold_dev_ms2: float
    refractory_s: float
    smooth_alpha: float


@dataclass(frozen=True, slots=True)
class ReadinessSettings:
    stationary_dev_max: float
    walk_cadence_spm: float
    run_cadence_spm: float
    run_hold_s: float
    hysteresis_spm: float
    turn_gyro_path_rad: float


@dataclass(frozen=True, slots=True)
class SpeedSettings:
    window_s: float
    min_speed_mps: float


@dataclass(frozen=True, slots=True)
class TrackSettings:
    leg_length_m: float
    zone_length_m: float
    entry_margin_m: float


@dataclass(frozen=True, slots=True)
class FusionSettings:
    gap_opt_min_m: float
    gap_opt_max_m: float
    gap_far_m: float
    speed_match_tol_mps: float
    early_start_margin_m: float
    stall_cadence_spm: float
    stall_s: float
    hold_s: float
    clear_s: float
    optimal_exit_s: float
    pass_gap_m: float
    pass_hold_s: float
    auto_handoff: bool
    data_gap_s: float


@dataclass(frozen=True, slots=True)
class CueSettings:
    go_trigger_m: float
    go_cue_eta_s: float
    cue_cooldown_s: float
    alert_cooldown_s: float
    vibrate_cue_ms: int
    vibrate_alert_ms: int
    alert_pulses: int
    alert_pause_ms: int


@dataclass(frozen=True, slots=True)
class ScoreSettings:
    start: float
    gap_target_m: float
    gap_penalty_per_m: float
    speed_penalty_per_mps: float
    alert_penalty: float
    clean_bonus: float


@dataclass(frozen=True, slots=True)
class EngineSettings:
    tick_s: float
    session_heartbeat_s: float
    max_clock_skew_s: float
    calibrate_default_m: float
    calibrate_min_m: float
    calibrate_max_m: float
    leg_min_m: float
    leg_max_m: float
    zone_min_m: float
    zone_max_m: float


@dataclass(frozen=True, slots=True)
class Settings:
    broker: BrokerSettings
    edge: EdgeSettings
    accel_steps: AccelStepSettings
    readiness: ReadinessSettings
    speed: SpeedSettings
    track: TrackSettings
    fusion: FusionSettings
    cue: CueSettings
    score: ScoreSettings
    engine: EngineSettings


@dataclass(frozen=True, slots=True)
class Runtime:
    """Konfigurasi algoritma ditambah identitas tim yang sudah divalidasi."""

    settings: Settings
    team_id: str
