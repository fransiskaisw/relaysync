"""Penyimpanan panjang langkah per peran di berkas JSON lokal pengguna."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from relaysync.domain.models import Role

log = logging.getLogger(__name__)

DEFAULT_PATH = Path.home() / ".relaysync" / "calibration.json"


class JsonCalibrationStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or DEFAULT_PATH

    def load(self, role: Role) -> float | None:
        value = self._read().get(role.value)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return float(value)

    def save(self, role: Role, step_len_m: float) -> None:
        data = self._read()
        data[role.value] = round(step_len_m, 4)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temp, self._path)  # penggantian atomik agar berkas tidak setengah tertulis

    def _read(self) -> dict[str, object]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            log.warning("Berkas kalibrasi %s rusak, diabaikan", self._path)
            return {}
        return data
