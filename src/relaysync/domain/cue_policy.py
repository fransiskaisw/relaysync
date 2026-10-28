"""Kapan cue GO dikirim ke pelari 2, plus cooldown generik."""
from __future__ import annotations

from dataclasses import dataclass

from .models import Readiness


class Cooldown:
    """Mencegah pengiriman berulang tanpa henti."""

    def __init__(self, period_s: float) -> None:
        self._period_s = period_s
        self._last_s: float | None = None

    def reset(self) -> None:
        self._last_s = None

    def ready(self, now_s: float) -> bool:
        return self._last_s is None or now_s - self._last_s >= self._period_s

    def mark(self, now_s: float) -> None:
        self._last_s = now_s


@dataclass(frozen=True, slots=True)
class CueRules:
    go_trigger_m: float
    go_cue_eta_s: float


def should_cue_go(remaining_m: float, eta_s: float | None, readiness2: Readiness | None,
                  rules: CueRules) -> bool:
    """GO bila pelari 1 cukup dekat ke zona (jarak atau ETA) dan pelari 2 belum berlari."""
    if readiness2 is Readiness.RUNNING:
        return False
    near = remaining_m <= rules.go_trigger_m
    soon = eta_s is not None and eta_s <= rules.go_cue_eta_s
    return near or soon
