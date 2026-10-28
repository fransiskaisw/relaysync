"""Pembaca sensor lewat `termux-sensor` (Termux:API) dengan pencarian nama otomatis."""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import IO, Any

from relaysync.domain.models import AccelSample, GyroSample, SensorBatch
from relaysync.ports import Clock, SensorUnavailable
from relaysync.settings.models import EdgeSettings

log = logging.getLogger(__name__)

VECTOR_SIZE = 3
LIST_TIMEOUT_S = 10.0
_AVOID = ("uncalibrated", "wake")  # urutan: hindari varian tak terkalibrasi, lalu wakeup


@dataclass(frozen=True, slots=True)
class ResolvedSensors:
    step: str | None
    accel: str | None
    gyro: str | None


def _squash(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _pick(available: Sequence[str], keyword: str) -> str | None:
    matches = [name for name in available if _squash(keyword) in _squash(name)]
    for avoid in _AVOID:
        narrowed = [name for name in matches if avoid not in name.lower()]
        matches = narrowed or matches
    return matches[0] if matches else None


def resolve_sensors(available: Sequence[str], edge: EdgeSettings, want_gyro: bool) -> ResolvedSensors:
    return ResolvedSensors(
        step=_pick(available, edge.step_sensor),
        accel=_pick(available, edge.accel_sensor),
        gyro=_pick(available, edge.gyro_sensor) if want_gyro else None,
    )


def list_sensor_names() -> list[str]:
    """Daftar nama sensor dari `termux-sensor -l`."""
    try:
        result = subprocess.run(["termux-sensor", "-l"], capture_output=True, text=True,
                                timeout=LIST_TIMEOUT_S, check=True)
        names = json.loads(result.stdout).get("sensors", [])
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError) as exc:
        raise SensorUnavailable(
            "termux-sensor -l gagal. Pasang: pkg install termux-api dan aplikasi Termux:API "
            "(lihat docs/SETUP.md)."
        ) from exc
    return [str(n) for n in names]


class TermuxSensor:
    def __init__(self, settings: EdgeSettings, clock: Clock, *, want_gyro: bool) -> None:
        self._settings = settings
        self._clock = clock
        self._want_gyro = want_gyro
        self._lock = threading.Lock()
        self._accel: list[AccelSample] = []
        self._gyro: list[GyroSample] = []
        self._step: int | None = None
        self._kinds: dict[str, str] = {}
        self._proc: subprocess.Popen[str] | None = None

    def read_batch(self, duration_s: float) -> SensorBatch:
        self._ensure_started()
        self._clock.sleep(duration_s)
        with self._lock:
            batch = SensorBatch(duration_s, tuple(self._accel), tuple(self._gyro), self._step)
            self._accel, self._gyro = [], []
        return batch

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        found = resolve_sensors(list_sensor_names(), self._settings, self._want_gyro)
        if found.accel is None:
            raise SensorUnavailable("accelerometer tidak ditemukan. Cek: termux-sensor -l")
        if found.step is None:
            log.warning("Step counter tidak ditemukan, langkah dihitung dari accelerometer.")
        if self._want_gyro and found.gyro is None:
            log.warning("Gyroscope tidak ditemukan, gyro_path_rad akan 0.")
        self._kinds = {n: k for n, k in ((found.step, "step"), (found.accel, "accel"),
                                         (found.gyro, "gyro")) if n}
        log.info("Sensor dipakai: %s", sorted(self._kinds))
        command = ["termux-sensor", "-s", ",".join(self._kinds), "-d",
                   str(self._settings.sample_interval_ms)]
        try:
            self._proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        except OSError as exc:
            raise SensorUnavailable("termux-sensor tidak bisa dijalankan.") from exc
        assert self._proc.stdout is not None
        threading.Thread(target=self._pump, args=(self._proc.stdout,), daemon=True).start()

    def _pump(self, stream: IO[str]) -> None:
        decoder = json.JSONDecoder()
        buffer = ""
        for line in stream:
            buffer = (buffer + line).lstrip()
            while buffer:
                try:
                    obj, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    break  # objek belum lengkap, tunggu baris berikutnya
                self._ingest(obj)
                buffer = buffer[end:].lstrip()

    def _ingest(self, obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        stamp = self._clock.monotonic_s()
        for name, body in obj.items():
            values = body.get("values") if isinstance(body, dict) else None
            kind = self._kinds.get(str(name))
            if kind is None or not isinstance(values, list) or not values:
                continue
            with self._lock:
                self._store(kind, values, stamp)

    def _store(self, kind: str, values: list[Any], stamp: float) -> None:
        if kind == "step":
            self._step = int(values[0])
        elif len(values) >= VECTOR_SIZE:
            xyz = (float(values[0]), float(values[1]), float(values[2]))
            if kind == "accel":
                self._accel.append(AccelSample(stamp, xyz))
            else:
                self._gyro.append(GyroSample(stamp, xyz))
