"""relaysync-edge: menjalankan satu edge (edge1 atau edge2) di HP atau laptop."""
from __future__ import annotations

import argparse
import logging
import random
import secrets
from pathlib import Path

from relaysync.adapters.console_actuator import ConsoleActuator
from relaysync.adapters.json_calibration_store import JsonCalibrationStore
from relaysync.adapters.mqtt_bus import MqttBus
from relaysync.adapters.simulated_sensor import RunnerProfile, SimulatedSensor
from relaysync.adapters.step_sources import MODES, build_step_source
from relaysync.adapters.system_clock import SystemClock
from relaysync.adapters.termux_actuator import TermuxActuator
from relaysync.adapters.termux_sensor import TermuxSensor
from relaysync.domain.models import Role
from relaysync.messaging.topics import TopicMap
from relaysync.ports import SensorReader, SensorUnavailable
from relaysync.services.edge_node import EdgeNode

from .common import configure_logging, runtime_or_exit, stop_on_signal

log = logging.getLogger(__name__)
RUN_ID_BYTES = 4
DEFAULT_SIM_CADENCE_SPM = 170.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relaysync-edge", description="Jalankan edge RelaySync.")
    parser.add_argument("--role", required=True, choices=[r.value for r in Role],
                        help="edge1 = pelari 1 (pembawa tongkat), edge2 = pelari 2 (penerima)")
    parser.add_argument("--steps-source", default="auto", choices=MODES,
                        help="auto: step counter, cadangan accelerometer; hw; accel")
    parser.add_argument("--simulate", action="store_true", help="pakai sensor simulasi (tanpa HP)")
    parser.add_argument("--sim-delay", type=float, default=0.0,
                        help="detik sebelum pelari simulasi mulai berlari")
    parser.add_argument("--sim-cadence", type=float, default=DEFAULT_SIM_CADENCE_SPM)
    parser.add_argument("--calibration-file", help="jalur berkas kalibrasi (default ~/.relaysync)")
    parser.add_argument("--config", help="jalur configs/default.yaml alternatif")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    configure_logging(args.verbose)
    runtime = runtime_or_exit(args.config, args.env_file)
    settings, role, clock = runtime.settings, Role(args.role), SystemClock()
    run_id = secrets.token_hex(RUN_ID_BYTES)
    sensor: SensorReader
    if args.simulate:
        profile = RunnerProfile(args.sim_delay, args.sim_cadence)
        sensor = SimulatedSensor(profile, clock, random.Random(), settings.edge.sample_interval_ms)
    else:
        sensor = TermuxSensor(settings.edge, clock, want_gyro=role is Role.EDGE2)
    console = ConsoleActuator()
    store_path = Path(args.calibration_file) if args.calibration_file else None
    topics = TopicMap(runtime.team_id)
    node = EdgeNode(
        role=role, run_id=run_id, settings=settings, topics=topics, sensor=sensor,
        steps=build_step_source(args.steps_source, settings.edge, settings.accel_steps),
        bus=MqttBus(settings.broker, f"relaysync-{role.value}-{run_id}"), clock=clock,
        actuator=console if args.simulate else TermuxActuator(console),
        calibration=JsonCalibrationStore(store_path))
    log.info("TEAM_ID=%s, topic dasar: %s", runtime.team_id, topics.root)
    try:
        node.run(stop_on_signal())
    except SensorUnavailable as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
