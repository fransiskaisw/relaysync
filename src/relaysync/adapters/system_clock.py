"""Implementasi Clock: waktu sistem dan jam manual untuk simulasi."""
from __future__ import annotations

import time

MS_PER_S = 1000


class SystemClock:
    def now_ms(self) -> int:
        return time.time_ns() // 1_000_000

    def monotonic_s(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ManualClock:
    """Jam yang maju hanya saat diperintah; sleep() memajukan waktu tanpa menunggu."""

    def __init__(self, start_ms: int = 1_790_000_000_000) -> None:
        self._now_ms = start_ms

    def now_ms(self) -> int:
        return self._now_ms

    def monotonic_s(self) -> float:
        return self._now_ms / MS_PER_S

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._now_ms += int(seconds * MS_PER_S)
