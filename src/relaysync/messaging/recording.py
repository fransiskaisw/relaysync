"""Format rekaman untuk tools/record_telemetry.py, simulate_race.py, dan mode replay."""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from relaysync.domain.models import Readiness, Role, StepsSource, Telemetry, WindowFeatures

from .errors import PayloadError

TELEMETRY_COLUMNS = (
    "received_ms", "dev", "run", "n_msg", "t_ms", "window_s", "steps_total", "dist_est_m",
    "step_len_m", "cadence_spm", "accel_dev_rms", "gyro_path_rad", "readiness", "steps_src",
    "calibrated",
)


@dataclass(frozen=True, slots=True)
class Record:
    topic: str
    received_ms: int
    payload: bytes


def to_json_line(record: Record) -> str:
    """Satu baris JSON; payload non-JSON (misal 'online') disimpan sebagai teks."""
    text = record.payload.decode("utf-8", errors="replace")
    try:
        body: Any = json.loads(text)
    except ValueError:
        body = text
    return json.dumps({"topic": record.topic, "received_ms": record.received_ms, "payload": body})


def _from_obj(obj: Any) -> Record:
    if not isinstance(obj, dict) or not {"topic", "received_ms", "payload"} <= set(obj):
        raise PayloadError("baris rekaman harus memuat topic, received_ms, payload")
    payload = obj["payload"]
    raw = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload).encode()
    return Record(str(obj["topic"]), int(obj["received_ms"]), raw)


def read_json_records(text: str) -> Iterator[Record]:
    """Baca JSONL (satu objek per baris) atau satu larik JSON."""
    stripped = text.strip()
    if stripped.startswith("["):
        for obj in json.loads(stripped):
            yield _from_obj(obj)
        return
    for line in stripped.splitlines():
        if line.strip():
            yield _from_obj(json.loads(line))


def telemetry_to_row(received_ms: int, t: Telemetry) -> list[Any]:
    f = t.features
    return [received_ms, t.dev.value, t.run, t.n_msg, t.t_ms, f.window_s, f.steps_total,
            f.dist_est_m, f.step_len_m, f.cadence_spm, f.accel_dev_rms,
            "" if f.gyro_path_rad is None else f.gyro_path_rad,
            "" if f.readiness is None else f.readiness.value, f.steps_src.value, f.calibrated]


def telemetry_csv(rows: Iterable[tuple[int, Telemetry]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(TELEMETRY_COLUMNS)
    for received_ms, tele in rows:
        writer.writerow(telemetry_to_row(received_ms, tele))
    return out.getvalue()


def read_telemetry_csv(text: str) -> Iterator[tuple[int, Telemetry]]:
    for row in csv.DictReader(io.StringIO(text)):
        try:
            gyro, ready = row["gyro_path_rad"], row["readiness"]
            features = WindowFeatures(
                window_s=float(row["window_s"]), steps_total=int(row["steps_total"]),
                dist_est_m=float(row["dist_est_m"]), step_len_m=float(row["step_len_m"]),
                cadence_spm=float(row["cadence_spm"]), accel_dev_rms=float(row["accel_dev_rms"]),
                steps_src=StepsSource(row["steps_src"]),
                calibrated=row["calibrated"].strip().lower() == "true",
                gyro_path_rad=float(gyro) if gyro != "" else None,
                readiness=Readiness(ready) if ready != "" else None,
            )
            yield int(row["received_ms"]), Telemetry(
                Role(row["dev"]), row["run"], int(row["n_msg"]), int(row["t_ms"]), features)
        except (KeyError, ValueError) as exc:
            raise PayloadError(f"baris CSV tidak valid: {exc}") from exc
