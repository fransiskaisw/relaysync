"""Memeriksa daftar sensor Termux:API dan pencocokan nama sensor RelaySync."""
from __future__ import annotations

import argparse

from relaysync.adapters.system_clock import SystemClock
from relaysync.adapters.termux_sensor import (
    TermuxSensor,
    list_sensor_names,
    resolve_sensors,
)
from relaysync.ports import SensorUnavailable
from relaysync.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Periksa sensor Termux:API yang tersedia di HP Android."
    )
    parser.add_argument("--config", help="jalur berkas konfigurasi YAML")
    parser.add_argument(
        "--sample-seconds",
        type=float,
        default=0.0,
        help="bila > 0, baca sampel sensor selama N detik untuk uji singkat",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings(args.config)
    try:
        names = list_sensor_names()
    except SensorUnavailable as exc:
        print(f"GAGAL membaca daftar sensor: {exc}")
        raise SystemExit(1) from exc

    print(f"Ditemukan {len(names)} sensor pada perangkat:")
    for idx, name in enumerate(names, start=1):
        print(f"  {idx:2d}. {name}")

    resolved = resolve_sensors(names, settings.edge, want_gyro=True)
    print("\nHasil pencocokan sensor untuk RelaySync:")
    print(f"  - Step Counter ({settings.edge.step_sensor}): {resolved.step or 'TIDAK ADA (pakai cadangan accel)'}")
    print(f"  - Accelerometer ({settings.edge.accel_sensor}): {resolved.accel or 'TIDAK DITEMUKAN'}")
    print(f"  - Gyroscope ({settings.edge.gyro_sensor}): {resolved.gyro or 'TIDAK DITEMUKAN'}")

    if args.sample_seconds > 0:
        print(f"\nMembaca sampel selama {args.sample_seconds:.1f} detik...")
        sensor = TermuxSensor(settings.edge, SystemClock(), want_gyro=True)
        try:
            batch = sensor.read_batch(args.sample_seconds)
        finally:
            sensor.close()
        print(
            f"Sampel terkumpul: accel={len(batch.accel)}, gyro={len(batch.gyro)}, "
            f"step_counter={batch.step_counter}"
        )


if __name__ == "__main__":
    main()
