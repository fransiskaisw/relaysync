"""relaysync-engine: menjalankan mesin estafet di laptop."""
from __future__ import annotations

import argparse
import logging
import secrets

from relaysync.adapters.mqtt_bus import MqttBus
from relaysync.adapters.system_clock import SystemClock
from relaysync.messaging.topics import TopicMap
from relaysync.services.relay_engine import RelayEngine

from .common import configure_logging, runtime_or_exit, stop_on_signal

log = logging.getLogger(__name__)
CLIENT_SUFFIX_BYTES = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relaysync-engine", description="Jalankan engine RelaySync.")
    parser.add_argument("--config", help="jalur configs/default.yaml alternatif")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    runtime = runtime_or_exit(args.config, args.env_file)
    topics = TopicMap(runtime.team_id)
    bus = MqttBus(runtime.settings.broker, f"relaysync-engine-{secrets.token_hex(CLIENT_SUFFIX_BYTES)}")
    engine = RelayEngine(settings=runtime.settings, topics=topics, bus=bus, clock=SystemClock())
    log.info("TEAM_ID=%s, lintasan %g m, zona %g m", runtime.team_id,
             runtime.settings.track.leg_length_m, runtime.settings.track.zone_length_m)
    engine.run(stop_on_signal())


if __name__ == "__main__":
    main()
