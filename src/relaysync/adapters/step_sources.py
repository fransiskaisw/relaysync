"""Sumber langkah: step counter perangkat keras, dan pemilih otomatis dengan cadangan."""
from __future__ import annotations

import logging
from collections import deque

from relaysync.adapters.accel_step_detector import AccelStepDetector
from relaysync.domain.models import SensorBatch, StepsSource
from relaysync.ports import StepSource
from relaysync.settings.models import AccelStepSettings, EdgeSettings

log = logging.getLogger(__name__)

MODES = ("auto", "hw", "accel")


class HardwareStepSource:
    """Step counter Android bersifat kumulatif sejak boot; kita hitung selisihnya."""

    name = StepsSource.HW.value

    def __init__(self) -> None:
        self._last: int | None = None
        self._baseline: int | None = None

    def update(self, batch: SensorBatch) -> int:
        if batch.step_counter is not None:
            self._last = batch.step_counter
            if self._baseline is None:
                self._baseline = self._last
        if self._last is None or self._baseline is None:
            return 0
        return max(0, self._last - self._baseline)

    def rebase(self) -> None:
        self._baseline = self._last


class AutoStepSource:
    """Memakai hw; berpindah ke accel (dan bertahan) bila hw diam padahal accel melihat langkah.

    Total yang dilaporkan dijaga monoton lewat offset saat berpindah sumber.
    """

    def __init__(self, hw: HardwareStepSource, accel: AccelStepDetector, mode: str,
                 stall_windows: int, min_accel_steps: int) -> None:
        self._hw, self._accel = hw, accel
        self._using_accel = mode == "accel"
        self._locked = mode != "auto"
        self._min_accel_steps = min_accel_steps
        self._history: deque[tuple[int, int]] = deque(maxlen=stall_windows + 1)
        self._offset = 0

    @property
    def name(self) -> str:
        return StepsSource.ACCEL.value if self._using_accel else StepsSource.HW.value

    def update(self, batch: SensorBatch) -> int:
        hw_total, accel_total = self._hw.update(batch), self._accel.update(batch)
        self._history.append((hw_total, accel_total))
        if not self._locked and self._hw_is_stalled():
            self._switch_to_accel(hw_total, accel_total)
        return self._reading(hw_total, accel_total)

    def rebase(self) -> None:
        self._hw.rebase()
        self._accel.rebase()
        self._offset = 0
        self._history.clear()

    def _hw_is_stalled(self) -> bool:
        if len(self._history) < (self._history.maxlen or 0):
            return False
        hw_first, accel_first = self._history[0]
        hw_last, accel_last = self._history[-1]
        return hw_last == hw_first and accel_last - accel_first >= self._min_accel_steps

    def _switch_to_accel(self, hw_total: int, accel_total: int) -> None:
        self._offset = (hw_total + self._offset) - accel_total
        self._using_accel = self._locked = True
        log.warning("Step counter perangkat keras tidak berubah saat ada gerakan "
                    "(izin Physical activity?). Beralih ke penghitung accelerometer.")

    def _reading(self, hw_total: int, accel_total: int) -> int:
        return (accel_total if self._using_accel else hw_total) + self._offset


def build_step_source(mode: str, edge: EdgeSettings, accel_cfg: AccelStepSettings) -> StepSource:
    if mode not in MODES:
        raise ValueError(f"mode sumber langkah tidak dikenal: {mode}")
    return AutoStepSource(HardwareStepSource(), AccelStepDetector(accel_cfg), mode,
                          edge.hw_stall_windows, edge.hw_stall_min_accel_steps)
