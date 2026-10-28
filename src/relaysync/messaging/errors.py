"""Exception khusus lapisan pesan."""
from __future__ import annotations


class PayloadError(ValueError):
    """Payload tidak sesuai skema."""


class TelemetryRejected(PayloadError):
    """Telemetry ditolak: bentuk salah, basi, atau urutan mundur."""


class CommandRejected(PayloadError):
    """Perintah kontrol tidak dikenal atau parameternya tidak sah."""


class TopicError(PayloadError):
    """Topic tidak mengikuti pola RELAYSYNC."""
