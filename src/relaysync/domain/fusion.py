"""Fusi aturan dua pelari: kondisi alert, zona optimal, latch, dan pewaktu."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .geometry import TrackGeometry
from .models import Readiness
from .states import AlertReason


@dataclass(frozen=True, slots=True)
class FusionRules:
    gap_opt_min_m: float
    gap_opt_max_m: float
    gap_far_m: float
    speed_match_tol_mps: float
    early_start_margin_m: float
    stall_cadence_spm: float


@dataclass(frozen=True, slots=True)
class FusionInputs:
    x1_m: float
    x2_m: float
    gap_m: float
    remaining_m: float
    v1_mps: float
    v2_mps: float
    cadence1_spm: float
    readiness2: Readiness | None


def build_inputs(geometry: TrackGeometry, dist1_m: float, dist2_m: float, v1_mps: float,
                 v2_mps: float, cadence1_spm: float, readiness2: Readiness | None) -> FusionInputs:
    x1, x2 = dist1_m, geometry.x2(dist2_m)
    return FusionInputs(x1, x2, x2 - x1, geometry.remaining_to_zone_m(x1), v1_mps, v2_mps,
                        cadence1_spm, readiness2)


def raw_alert_reason(inp: FusionInputs, geometry: TrackGeometry,
                     rules: FusionRules) -> AlertReason | None:
    """Kondisi alert sesaat (tanpa durasi). Prioritas: sebab spesifik lebih dulu."""
    running = inp.readiness2 is Readiness.RUNNING
    if geometry.zone_exceeded(inp.x1_m):
        return AlertReason.ZONE_EXCEEDED
    if running and inp.remaining_m > rules.early_start_margin_m:
        return AlertReason.EARLY_START
    if running and inp.cadence1_spm < rules.stall_cadence_spm:
        return AlertReason.RUNNER1_STALLED
    if running and inp.gap_m > rules.gap_far_m:
        return AlertReason.GAP_TOO_FAR
    return None


def is_optimal(inp: FusionInputs, geometry: TrackGeometry, rules: FusionRules) -> bool:
    return (
        geometry.in_entry_window(inp.x1_m)
        and inp.readiness2 is Readiness.RUNNING
        and rules.gap_opt_min_m <= inp.gap_m <= rules.gap_opt_max_m
        and abs(inp.v1_mps - inp.v2_mps) < rules.speed_match_tol_mps
    )


class AlertLatch:
    """Alert menyala setelah kondisi bertahan hold, padam setelah pulih clear_s atau ack."""

    def __init__(self, hold_s: Mapping[AlertReason, float], clear_s: float) -> None:
        self._hold = hold_s
        self._clear_s = clear_s
        self.reset()

    def reset(self) -> None:
        self._active: AlertReason | None = None
        self._candidate: AlertReason | None = None
        self._since = 0.0
        self._clear_since: float | None = None
        self._suppressed: AlertReason | None = None

    @property
    def active(self) -> AlertReason | None:
        return self._active

    def ack(self) -> None:
        """Padamkan alert; alasan yang sama tidak menyala lagi sampai kondisi berubah."""
        self._suppressed = self._active or self._candidate
        self._active = None
        self._clear_since = None

    def update(self, raw: AlertReason | None, now_s: float) -> AlertReason | None:
        if raw is not self._candidate:
            self._candidate, self._since = raw, now_s
        if self._suppressed is not None and raw is not self._suppressed:
            self._suppressed = None
        if self._active is None:
            self._maybe_raise(raw, now_s)
        else:
            self._maybe_clear(raw, now_s)
        return self._active

    def _maybe_raise(self, raw: AlertReason | None, now_s: float) -> None:
        if raw is not None and raw is not self._suppressed and now_s - self._since >= self._hold[raw]:
            self._active, self._clear_since = raw, None

    def _maybe_clear(self, raw: AlertReason | None, now_s: float) -> None:
        if raw is None:
            if self._clear_since is None:
                self._clear_since = now_s
            elif now_s - self._clear_since >= self._clear_s:
                self._active, self._clear_since = None, None
            return
        self._clear_since = None
        if raw is not self._active and now_s - self._since >= self._hold[raw]:
            self._active = raw


class HoldTimer:
    """True setelah kondisi aktif terus-menerus selama required_s."""

    def __init__(self, required_s: float) -> None:
        self._required_s = required_s
        self._since: float | None = None

    def reset(self) -> None:
        self._since = None

    def update(self, active: bool, now_s: float) -> bool:
        if not active:
            self._since = None
            return False
        if self._since is None:
            self._since = now_s
        return now_s - self._since >= self._required_s


class ReleaseDelay:
    """Menyala seketika, padam hanya setelah tidak aktif selama release_s (anti kedip)."""

    def __init__(self, release_s: float) -> None:
        self._release_s = release_s
        self._on = False
        self._off_since: float | None = None

    def reset(self) -> None:
        self._on, self._off_since = False, None

    def update(self, active: bool, now_s: float) -> bool:
        if active:
            self._on, self._off_since = True, None
        elif self._on:
            if self._off_since is None:
                self._off_since = now_s
            elif now_s - self._off_since >= self._release_s:
                self._on, self._off_since = False, None
        return self._on
