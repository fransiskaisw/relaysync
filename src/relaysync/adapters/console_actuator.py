"""Aktuator pengganti: menulis aksi ke log (dipakai bila Termux:API tidak ada)."""
from __future__ import annotations

import logging
from collections.abc import Sequence

log = logging.getLogger(__name__)


class ConsoleActuator:
    def vibrate(self, pulses_ms: Sequence[int], pause_ms: int) -> None:
        log.info("[GETAR] pola %s ms, jeda %d ms", list(pulses_ms), pause_ms)

    def cancel_vibration(self) -> None:
        log.info("[GETAR] dibatalkan")

    def notify(self, title: str, text: str, notification_id: str) -> None:
        log.info("[NOTIFIKASI %s] %s: %s", notification_id, title, text)

    def clear_notification(self, notification_id: str) -> None:
        log.info("[NOTIFIKASI %s] dihapus", notification_id)
