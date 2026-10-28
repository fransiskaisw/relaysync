"""Aktuator Termux:API: termux-vibrate dan termux-notification.

Argumen selalu dikirim sebagai daftar (tanpa shell), sehingga teks dari jaringan
tidak pernah dieksekusi sebagai perintah.
"""
from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Sequence

from relaysync.ports import Actuator

log = logging.getLogger(__name__)

COMMAND_TIMEOUT_S = 5.0
MS_PER_S = 1000.0


class TermuxActuator:
    def __init__(self, fallback: Actuator) -> None:
        self._fallback = fallback
        self._cancel = threading.Event()

    def vibrate(self, pulses_ms: Sequence[int], pause_ms: int) -> None:
        self.cancel_vibration()
        self._cancel = threading.Event()
        worker = threading.Thread(
            target=self._play, args=(tuple(pulses_ms), pause_ms, self._cancel), daemon=True
        )
        worker.start()

    def cancel_vibration(self) -> None:
        self._cancel.set()

    def notify(self, title: str, text: str, notification_id: str) -> None:
        command = ["termux-notification", "--id", notification_id, "--title", title,
                   "--content", text, "--priority", "high"]
        if not self._run(command):
            self._fallback.notify(title, text, notification_id)

    def clear_notification(self, notification_id: str) -> None:
        if not self._run(["termux-notification-remove", notification_id]):
            self._fallback.clear_notification(notification_id)

    def _play(self, pulses: tuple[int, ...], pause_ms: int, cancel: threading.Event) -> None:
        for duration in pulses:
            if cancel.is_set():
                return
            if not self._run(["termux-vibrate", "-f", "-d", str(duration)]):
                self._fallback.vibrate(pulses, pause_ms)
                return
            cancel.wait((duration + pause_ms) / MS_PER_S)

    def _run(self, command: list[str]) -> bool:
        try:
            subprocess.run(command, check=True, timeout=COMMAND_TIMEOUT_S,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("%s gagal (%s), memakai fallback konsol", command[0], exc)
            return False
        return True
