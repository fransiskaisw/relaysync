"""Status sesi, kode alasan alert, dan fungsi transisi murni."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    IDLE = "IDLE"
    APPROACHING = "APPROACHING"
    OPTIMAL_TRANSFER_ZONE = "OPTIMAL_TRANSFER_ZONE"
    GAP_TOO_FAR_ALERT = "GAP_TOO_FAR_ALERT"
    HANDOFF_DONE = "HANDOFF_DONE"
    NO_DATA = "NO_DATA"


class AlertReason(str, Enum):
    GAP_TOO_FAR = "GAP_TOO_FAR"
    EARLY_START = "EARLY_START"
    RUNNER1_STALLED = "RUNNER1_STALLED"
    ZONE_EXCEEDED = "ZONE_EXCEEDED"


STATE_LABELS: dict[State, str] = {
    State.IDLE: "Menunggu",
    State.APPROACHING: "Pelari 1 mendekat",
    State.OPTIMAL_TRANSFER_ZONE: "Zona serah terima optimal",
    State.GAP_TOO_FAR_ALERT: "Peringatan jarak",
    State.HANDOFF_DONE: "Serah terima selesai",
    State.NO_DATA: "Data terputus",
}

STATE_REASONS: dict[State, str] = {
    State.IDLE: "Sesi belum dimulai atau salah satu HP belum mengirim data.",
    State.APPROACHING: "Pelari 1 bergerak dan masih jauh dari zona.",
    State.OPTIMAL_TRANSFER_ZONE: "Posisi, jarak antar pelari, dan kecepatan sesuai.",
    State.HANDOFF_DONE: "Serah terima tercatat.",
    State.NO_DATA: "Salah satu HP berhenti mengirim data.",
}

ALERT_TEXT: dict[AlertReason, str] = {
    AlertReason.GAP_TOO_FAR: "Jarak antar pelari terlalu jauh.",
    AlertReason.EARLY_START: "Pelari 2 berlari terlalu awal.",
    AlertReason.RUNNER1_STALLED: "Pelari 1 melambat, pelari 2 sudah berlari.",
    AlertReason.ZONE_EXCEEDED: "Pelari 1 melewati zona tanpa serah terima.",
}


@dataclass(frozen=True, slots=True)
class StateFacts:
    active: bool
    seen_both: bool
    stale: bool
    handed_off: bool
    alert_active: bool
    optimal: bool


def transition(facts: StateFacts) -> State:
    """Pilih status berdasarkan prioritas tetap (lihat docs/ALGORITHM.md)."""
    if not facts.active:
        return State.IDLE
    if facts.handed_off:
        return State.HANDOFF_DONE
    if not facts.seen_both:
        return State.IDLE
    if facts.stale:
        return State.NO_DATA
    if facts.alert_active:
        return State.GAP_TOO_FAR_ALERT
    if facts.optimal:
        return State.OPTIMAL_TRANSFER_ZONE
    return State.APPROACHING
