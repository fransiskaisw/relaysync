"""Processing 2 (bagian 2): energi gerak dan kesiapan lari."""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .geometry import STANDARD_GRAVITY, magnitude
from .models import AccelSample, GyroSample, Readiness


def accel_dev_rms(samples: Sequence[AccelSample]) -> float:
    """Akar rata-rata kuadrat dari (|a| - 9,81): energi gerak di luar gravitasi."""
    if not samples:
        return 0.0
    total = sum((magnitude(s.xyz) - STANDARD_GRAVITY) ** 2 for s in samples)
    return math.sqrt(total / len(samples))


def gyro_path_rad(samples: Sequence[GyroSample], max_dt_s: float) -> float:
    """Jumlah |omega| x dt; celah lebih besar dari max_dt_s tidak diintegrasi."""
    path = 0.0
    for before, current in zip(samples, samples[1:], strict=False):
        dt = current.t_s - before.t_s
        if 0.0 < dt <= max_dt_s:
            path += magnitude(current.xyz) * dt
    return path


@dataclass(frozen=True, slots=True)
class ReadinessRules:
    stationary_dev_max: float
    walk_cadence_spm: float
    run_cadence_spm: float
    run_hold_s: float
    hysteresis_spm: float
    turn_gyro_path_rad: float


class ReadinessClassifier:
    """STATIONARY, ARMING, RUNNING dengan histeresis dan waktu tahan masuk RUNNING."""

    def __init__(self, rules: ReadinessRules) -> None:
        self._rules = rules
        self._running = False
        self._above_s = 0.0

    def reset(self) -> None:
        self._running = False
        self._above_s = 0.0

    def update(self, accel_dev: float, cadence_spm: float, gyro_path: float,
               window_s: float) -> Readiness:
        rules = self._rules
        if self._running:
            if cadence_spm >= rules.run_cadence_spm - rules.hysteresis_spm:
                return Readiness.RUNNING
            self._running = False
        if cadence_spm >= rules.run_cadence_spm:
            self._above_s += window_s
            if self._above_s >= rules.run_hold_s:
                self._running = True
                return Readiness.RUNNING
            return Readiness.ARMING
        self._above_s = 0.0
        calm = accel_dev < rules.stationary_dev_max and gyro_path < rules.turn_gyro_path_rad
        if calm and cadence_spm < rules.walk_cadence_spm:
            return Readiness.STATIONARY
        return Readiness.ARMING
