"""Antarmuka (Protocol) ke dunia luar. Domain dan service hanya bergantung ke sini."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from relaysync.domain.models import Role, SensorBatch

MessageHandler = Callable[[str, bytes], None]


class SensorUnavailable(RuntimeError):
    """Sensor tidak bisa dibaca (perintah hilang, izin ditolak, dan sebagainya)."""


@dataclass(frozen=True, slots=True)
class LastWill:
    topic: str
    payload: bytes
    retain: bool = True


class Clock(Protocol):
    def now_ms(self) -> int: ...
    def monotonic_s(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SensorReader(Protocol):
    def read_batch(self, duration_s: float) -> SensorBatch:
        """Blok selama `duration_s`, lalu kembalikan sampel yang terkumpul."""
        ...

    def close(self) -> None: ...


class StepSource(Protocol):
    @property
    def name(self) -> str:
        """'hw' atau 'accel' (sumber yang sedang dipakai)."""
        ...

    def update(self, batch: SensorBatch) -> int:
        """Langkah kumulatif sejak rebase terakhir."""
        ...

    def rebase(self) -> None:
        """Mulai hitung dari nol (awal sesi, percobaan baru)."""
        ...


class MessageBus(Protocol):
    def connect(self, will: LastWill | None) -> None: ...
    def disconnect(self) -> None: ...
    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None: ...
    def subscribe(self, topic_filter: str, handler: MessageHandler, *, qos: int = 1) -> None: ...
    def add_connect_hook(self, hook: Callable[[], None]) -> None:
        """Dipanggil setiap kali (re)connect berhasil."""
        ...


class Actuator(Protocol):
    def vibrate(self, pulses_ms: Sequence[int], pause_ms: int) -> None: ...
    def cancel_vibration(self) -> None: ...
    def notify(self, title: str, text: str, notification_id: str) -> None: ...
    def clear_notification(self, notification_id: str) -> None: ...


class CalibrationStore(Protocol):
    def load(self, role: Role) -> float | None:
        """Panjang langkah tersimpan (m), atau None."""
        ...

    def save(self, role: Role, step_len_m: float) -> None: ...
