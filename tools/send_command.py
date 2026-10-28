"""Mengirim perintah kontrol ke topic relaysync/<TEAM_ID>/control lewat CLI."""
from __future__ import annotations

import argparse
import secrets
import time

from relaysync.adapters.mqtt_bus import MqttBus
from relaysync.apps.common import configure_logging, runtime_or_exit
from relaysync.domain.models import Role
from relaysync.messaging.codec import (
    CommandName,
    ControlCommand,
    decode_command,
    encode_command,
    limits_from_settings,
)
from relaysync.messaging.topics import TopicMap


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kirim perintah kontrol ke RelaySync (start, stop, reset, ack, handoff, calibrate_step, config, new_attempt)."
    )
    parser.add_argument(
        "cmd",
        choices=[c.value for c in CommandName],
        help="nama perintah yang diizinkan",
    )
    parser.add_argument(
        "--target",
        choices=[r.value for r in Role],
        help="target perangkat untuk calibrate_step (edge1 atau edge2)",
    )
    parser.add_argument("--distance-m", type=float, help="jarak kalibrasi dalam meter (default 20)")
    parser.add_argument("--leg-length-m", type=float, help="posisi awal zona Z dalam meter")
    parser.add_argument("--zone-length-m", type=float, help="panjang zona transisi dalam meter")
    parser.add_argument("--config", help="jalur configs/default.yaml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    runtime = runtime_or_exit(args.config, args.env_file)
    limits = limits_from_settings(runtime.settings)
    cmd = ControlCommand(
        name=CommandName(args.cmd),
        target=Role(args.target) if args.target else None,
        distance_m=args.distance_m,
        leg_length_m=args.leg_length_m,
        zone_length_m=args.zone_length_m,
    )
    payload = encode_command(cmd)
    decode_command(payload, limits)

    topics = TopicMap(runtime.team_id)
    bus = MqttBus(runtime.settings.broker, f"relaysync-cmd-{secrets.token_hex(3)}")
    bus.connect(None)
    if not bus.wait_connected(8.0):
        bus.disconnect()
        raise SystemExit("Gagal terhubung ke broker MQTT dalam 8 detik.")
    try:
        bus.publish(topics.control, payload, qos=1)
        time.sleep(0.3)
        print(f"Perintah terkirim ke {topics.control}: {payload.decode('utf-8')}")
    finally:
        bus.disconnect()


if __name__ == "__main__":
    main()
