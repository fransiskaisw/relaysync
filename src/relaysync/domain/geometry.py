"""Geometri lintasan estafet 1 dimensi dan operasi vektor dasar."""
from __future__ import annotations

import math
from dataclasses import dataclass

Vec3 = tuple[float, float, float]
STANDARD_GRAVITY = 9.81


def magnitude(v: Vec3) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


@dataclass(frozen=True, slots=True)
class TrackGeometry:
    """Pelari 1 mulai di x=0; pelari 2 menunggu di awal zona Z = leg_length_m."""

    leg_length_m: float
    zone_length_m: float
    entry_margin_m: float

    def x2(self, dist2_m: float) -> float:
        return self.leg_length_m + dist2_m

    def remaining_to_zone_m(self, x1_m: float) -> float:
        return self.leg_length_m - x1_m

    def in_entry_window(self, x1_m: float) -> bool:
        """x1 berada di [Z - margin, Z + panjang zona]."""
        low = self.leg_length_m - self.entry_margin_m
        return low <= x1_m <= self.leg_length_m + self.zone_length_m

    def zone_exceeded(self, x1_m: float) -> bool:
        return x1_m > self.leg_length_m + self.zone_length_m


def eta_to_zone_s(remaining_m: float, v1_mps: float, min_speed_mps: float) -> float | None:
    """Estimasi waktu tiba ke Z; None bila v1 terlalu kecil. 0 bila sudah lewat."""
    if v1_mps <= min_speed_mps:
        return None
    return max(0.0, remaining_m) / v1_mps
