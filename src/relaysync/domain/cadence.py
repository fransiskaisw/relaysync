"""Processing 2 (bagian 1): kadens langkah per menit dari jendela geser."""
from __future__ import annotations

from collections import deque

S_PER_MIN = 60.0
MIN_SPAN_S = 1.0  # rentang minimum agar kadens tidak melonjak karena data sedikit


class CadenceCounter:
    """Kadens = selisih langkah di jendela geser / durasi jendela x 60.

    Jendela geser dipakai karena step counter perangkat keras dapat tertunda
    (batching), sehingga hitungan per detik terlalu bergerigi.
    """

    def __init__(self, window_s: float) -> None:
        self._window_s = window_s
        self._points: deque[tuple[float, int]] = deque()

    def clear(self) -> None:
        self._points.clear()

    def record(self, at_s: float, steps_total: int) -> None:
        if self._points and steps_total < self._points[-1][1]:
            self._points.clear()  # hitungan mundur: sesi di-rebase
        self._points.append((at_s, steps_total))
        horizon = at_s - self._window_s
        while len(self._points) > 1 and self._points[1][0] <= horizon:
            self._points.popleft()

    def cadence_spm(self) -> float:
        if len(self._points) < 2:
            return 0.0
        (t0, s0), (t1, s1) = self._points[0], self._points[-1]
        span = t1 - t0
        if span < MIN_SPAN_S:
            return 0.0
        return (s1 - s0) / span * S_PER_MIN
