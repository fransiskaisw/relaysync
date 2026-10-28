"""Sensor simulasi pelari untuk mencoba RelaySync tanpa HP."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from relaysync.domain.geometry import STANDARD_GRAVITY
from relaysync.domain.models import AccelSample, GyroSample, SensorBatch
from relaysync.ports import Clock

STEP_AMPLITUDE_MS2 = 6.0
IDLE_NOISE_MS2 = 0.05
RUN_GYRO_RAD_S = 1.5
IDLE_GYRO_RAD_S = 0.02
TWO_PI = 2 * math.pi
S_PER_MIN = 60.0
MS_PER_S = 1000.0


@dataclass(frozen=True, slots=True)
class RunnerProfile:
    start_delay_s: float
    cadence_spm: float
    step_counter_base: int = 12_000  # step counter asli kumulatif sejak boot


class SimulatedSensor:
    def __init__(self, profile: RunnerProfile, clock: Clock, rng: random.Random,
                 sample_interval_ms: int) -> None:
        self._profile = profile
        self._clock = clock
        self._rng = rng
        self._dt = sample_interval_ms / MS_PER_S
        self._origin = clock.monotonic_s()
        self._phase = 0.0  # satu putaran penuh = satu langkah

    def read_batch(self, duration_s: float) -> SensorBatch:
        self._clock.sleep(duration_s)
        end = self._clock.monotonic_s()
        count = max(1, int(duration_s / self._dt))
        accel, gyro = [], []
        for i in range(count):
            t = end - duration_s + i * self._dt
            running = t - self._origin >= self._profile.start_delay_s
            self._phase += TWO_PI * (self._profile.cadence_spm / S_PER_MIN) * self._dt if running else 0.0
            swing = STEP_AMPLITUDE_MS2 * math.sin(self._phase) if running else 0.0
            noise = self._rng.gauss(0, IDLE_NOISE_MS2)
            accel.append(AccelSample(t, (noise, noise, STANDARD_GRAVITY + swing + noise)))
            spin = RUN_GYRO_RAD_S if running else IDLE_GYRO_RAD_S
            gyro.append(GyroSample(t, (self._rng.gauss(0, spin), 0.0, 0.0)))
        steps = int(self._phase // TWO_PI)
        return SensorBatch(duration_s, tuple(accel), tuple(gyro),
                           self._profile.step_counter_base + steps)

    def close(self) -> None:
        return None
