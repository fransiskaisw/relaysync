"""Exception khusus konfigurasi."""
from __future__ import annotations


class ConfigError(Exception):
    """Konfigurasi tidak valid atau tidak ditemukan."""


class TeamIdError(ConfigError):
    """TEAM_ID kosong, masih placeholder, atau formatnya salah."""
