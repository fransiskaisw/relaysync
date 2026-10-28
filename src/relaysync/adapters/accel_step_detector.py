"""Penghitung langkah cadangan dari accelerometer: deteksi puncak dengan periode refrakter."""
from __future__ import annotations

from relaysync.domain.geometry import STANDARD_GRAVITY, magnitude
from relaysync.domain.models import AccelSample, SensorBatch
from relaysync.settings.models import AccelStepSettings


class AccelStepDetector:
    """Satu langkah = puncak lokal dari (|a| - 9,81) yang dihaluskan dan melewati ambang."""

    name = "accel"

    def __init__(self, settings: AccelStepSettings) -> None:
        self._cfg = settings
        self._smooth: float | None = None
        self._prev: tuple[float, float] | None = None  # (nilai, waktu) sampel sebelumnya
        self._prev2_value: float | None = None
        self._last_step_s = float("-inf")
        self._total = 0

    def rebase(self) -> None:
        self._total = 0

    def update(self, batch: SensorBatch) -> int:
        for sample in batch.accel:
            self._feed(sample)
        return self._total

    def _feed(self, sample: AccelSample) -> None:
        dev = magnitude(sample.xyz) - STANDARD_GRAVITY
        alpha = self._cfg.smooth_alpha
        self._smooth = dev if self._smooth is None else alpha * dev + (1 - alpha) * self._smooth
        if self._prev is not None and self._prev2_value is not None:
            value, at_s = self._prev
            is_peak = value > self._prev2_value and value >= self._smooth
            if (is_peak and value >= self._cfg.threshold_dev_ms2
                    and at_s - self._last_step_s >= self._cfg.refractory_s):
                self._total += 1
                self._last_step_s = at_s
        self._prev2_value = self._prev[0] if self._prev else None
        self._prev = (self._smooth, sample.t_s)
