"""Merekam paket MQTT RelaySync langsung dari broker ke berkas JSONL dan CSV."""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path

from relaysync.adapters.mqtt_bus import MqttBus
from relaysync.adapters.system_clock import SystemClock
from relaysync.apps.common import configure_logging, runtime_or_exit, stop_on_signal
from relaysync.messaging import codec
from relaysync.messaging.errors import PayloadError
from relaysync.messaging.recording import Record, telemetry_csv, to_json_line
from relaysync.messaging.topics import KIND_TELEMETRY, TopicMap
from relaysync.domain.models import Telemetry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rekam lalu lintas MQTT RelaySync ke berkas JSONL atau CSV untuk replay."
    )
    parser.add_argument(
        "--out",
        default="recordings/live_session.jsonl",
        help="jalur berkas keluaran (.jsonl atau .csv)",
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=0.0,
        help="durasi rekam dalam detik (0 = sampai Ctrl+C)",
    )
    parser.add_argument("--config", help="jalur configs/default.yaml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    runtime = runtime_or_exit(args.config, args.env_file)
    topics = TopicMap(runtime.team_id)
    clock = SystemClock()
    records: list[Record] = []
    tele_rows: list[tuple[int, Telemetry]] = []

    def on_msg(topic: str, payload: bytes) -> None:
        now = clock.now_ms()
        records.append(Record(topic, now, payload))
        if topic.startswith(f"{topics.root}/edge/"):
            try:
                role, kind = topics.parse_edge(topic)
                if kind == KIND_TELEMETRY:
                    tele = codec.decode_telemetry(role, payload, now_ms=now, max_skew_s=None)
                    tele_rows.append((now, tele))
            except PayloadError:
                pass

    bus = MqttBus(runtime.settings.broker, f"relaysync-rec-{secrets.token_hex(3)}")
    for t in topics.all_topics():
        bus.subscribe(t, on_msg)
    bus.connect(None)
    stop = stop_on_signal()
    start_s = clock.monotonic_s()
    print(f"Merekam topic di bawah {topics.root}/* (tekan Ctrl+C untuk berhenti)...")
    try:
        while not stop.is_set():
            clock.sleep(0.25)
            if args.duration_s > 0 and (clock.monotonic_s() - start_s) >= args.duration_s:
                break
    finally:
        bus.disconnect()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".csv":
        out_path.write_text(telemetry_csv(tele_rows), encoding="utf-8")
        print(f"Tersimpan {len(tele_rows)} baris telemetry ke {out_path}")
    else:
        lines = "\n".join(to_json_line(r) for r in records) + ("\n" if records else "")
        out_path.write_text(lines, encoding="utf-8")
        print(f"Tersimpan {len(records)} paket MQTT ke {out_path}")


if __name__ == "__main__":
    main()
