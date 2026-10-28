"""Identitas proyek: validasi TEAM_ID dan saran nilai unik."""
from __future__ import annotations

import re
import secrets
import string

from .errors import TeamIdError

PLACEHOLDER_TEAM_ID = "relaysync-kelompok-GANTI"
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{6,48}$")
_SUFFIX_LENGTH = 4
_ALPHABET = string.ascii_lowercase + string.digits


def suggest_team_id() -> str:
    """Saran TEAM_ID dengan sufiks acak 4 karakter."""
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(_SUFFIX_LENGTH))
    return f"relaysync-kelompok-{suffix}"


def validate_team_id(value: str | None) -> str:
    """Kembalikan TEAM_ID bila layak; tolak placeholder atau format salah."""
    text = (value or "").strip()
    if not text or text == PLACEHOLDER_TEAM_ID or text.upper().endswith("GANTI"):
        raise TeamIdError(
            "TEAM_ID masih kosong atau placeholder. Broker HiveMQ bersifat publik, "
            "jadi TEAM_ID harus unik per kelompok.\n"
            f"Saran nilai: TEAM_ID={suggest_team_id()}\n"
            "Isi di berkas .env (salin dari .env.example)."
        )
    if not _VALID_ID.match(text):
        raise TeamIdError(
            "TEAM_ID hanya boleh huruf, angka, '-' dan '_' (6 sampai 48 karakter). "
            f"Saran nilai: {suggest_team_id()}"
        )
    return text
