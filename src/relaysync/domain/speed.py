"""Kecepatan sebagai turunan numerik jarak pada jendela geser."""
from __future__ import annotations

from collections import deque

MIN_SPAN_S = 1.0


class SpeedEstimator:
    def __init__(self, window_s: float) -> None:
        self._window_s = window_s
        self._points: deque[tuple[float, float]] = deque()

    def clear(self) -> None:
        self._points.clear()

    def record(self, at_s: float, dist_m: float) -> None:
        if self._points and dist_m < self._points[-1][1]:
            self._points.clear()  # jarak mundur: edge di-rebase
        self._points.append((at_s, dist_m))
        horizon = at_s - self._window_s
        while len(self._points) > 1 and self._points[1][0] <= horizon:
            self._points.popleft()

    def speed_mps(self) -> float:
        if len(self._points) < 2:
            return 0.0
        (t0, d0), (t1, d1) = self._points[0], self._points[-1]
        span = t1 - t0
        return (d1 - d0) / span if span >= MIN_SPAN_S else 0.0
