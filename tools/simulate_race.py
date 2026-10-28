"""Generator skenario simulasi lari estafet ke berkas JSONL dan CSV (atau ke broker MQTT)."""
from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

from relaysync.adapters.console_actuator import ConsoleActuator
from relaysync.adapters.json_calibration_store import JsonCalibrationStore
from relaysync.adapters.memory_bus import MemoryBroker, MemoryBus
from relaysync.adapters.simulated_sensor import RunnerProfile, SimulatedSensor
from relaysync.adapters.step_sources import build_step_source
from relaysync.adapters.system_clock import ManualClock
from relaysync.domain.models import Role, Telemetry
from relaysync.messaging import codec
from relaysync.messaging.errors import PayloadError
from relaysync.messaging.recording import Record, telemetry_csv, to_json_line
from relaysync.messaging.topics import KIND_TELEMETRY, TopicMap
from relaysync.services.edge_node import EdgeNode
from relaysync.services.relay_engine import RelayEngine
from relaysync.settings import load_settings


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    description: str
    duration_s: int
    edge1_delay_s: float
    edge1_cadence_spm: float
    edge2_delay_s: float
    edge2_cadence_spm: float
    drop_edge2_at_s: int | None = None


SCENARIOS: dict[str, ScenarioSpec] = {
    "optimal": ScenarioSpec(
        description="Pendekatan normal, pelari 2 mulai saat cue GO, serah terima di zona optimal",
        duration_s=28,
        edge1_delay_s=0.0,
        edge1_cadence_spm=176.0,
        edge2_delay_s=14.0,
        edge2_cadence_spm=172.0,
    ),
    "early_start": ScenarioSpec(
        description="Pelari 2 berlari terlalu awal saat pelari 1 masih jauh (EARLY_START)",
        duration_s=25,
        edge1_delay_s=0.0,
        edge1_cadence_spm=165.0,
        edge2_delay_s=2.0,
        edge2_cadence_spm=175.0,
    ),
    "gap_too_far": ScenarioSpec(
        description="Pelari 2 berlari terlalu cepat sehingga jarak melebar (GAP_TOO_FAR)",
        duration_s=26,
        edge1_delay_s=0.0,
        edge1_cadence_spm=155.0,
        edge2_delay_s=10.0,
        edge2_cadence_spm=205.0,
    ),
    "no_data": ScenarioSpec(
        description="HP edge2 terputus di tengah lari sehingga memicu status NO_DATA",
        duration_s=24,
        edge1_delay_s=0.0,
        edge1_cadence_spm=170.0,
        edge2_delay_s=12.0,
        edge2_cadence_spm=170.0,
        drop_edge2_at_s=14,
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hasilkan berkas rekaman simulasi estafet (JSONL dan CSV) untuk mode replay dashboard."
    )
    parser.add_argument(
        "--scenario",
        default="optimal",
        choices=list(SCENARIOS),
        help="skenario simulasi yang dihasilkan",
    )
    parser.add_argument(
        "--out-dir",
        default="recordings",
        help="folder penyimpanan berkas .jsonl dan .csv",
    )
    parser.add_argument("--team-id", default="relaysync-simulasi")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--config", help="jalur configs/default.yaml")
    return parser


def run_scenario(
    spec: ScenarioSpec, team_id: str, seed: int, config_path: str | None
) -> tuple[list[Record], list[tuple[int, Telemetry]]]:
    settings = load_settings(config_path, env={})
    topics = TopicMap(team_id)
    clock = ManualClock()
    broker = MemoryBroker()
    records: list[Record] = []
    tele_rows: list[tuple[int, Telemetry]] = []

    def tap(topic: str, payload: bytes) -> None:
        now = clock.now_ms()
        records.append(Record(topic, now, payload))
        if topic.startswith(f"{topics.root}/edge/"):
            try:
                role, kind = topics.parse_edge(topic)
                if kind == KIND_TELEMETRY:
                    t = codec.decode_telemetry(role, payload, now_ms=now, max_skew_s=None)
                    tele_rows.append((now, t))
            except PayloadError:
                pass

    for t in topics.all_topics():
        broker.subscribe(t, tap)

    eng_bus = MemoryBus(broker)
    engine = RelayEngine(settings=settings, topics=topics, bus=eng_bus, clock=clock)
    engine.open()

    rng1, rng2 = random.Random(seed), random.Random(seed + 1)
    s1 = SimulatedSensor(
        RunnerProfile(spec.edge1_delay_s, spec.edge1_cadence_spm),
        clock,
        rng1,
        settings.edge.sample_interval_ms,
    )
    s2 = SimulatedSensor(
        RunnerProfile(spec.edge2_delay_s, spec.edge2_cadence_spm),
        clock,
        rng2,
        settings.edge.sample_interval_ms,
    )
    bus1, bus2 = MemoryBus(broker), MemoryBus(broker)
    cal_path = Path("/tmp/relaysync_sim_cal.json")
    node1 = EdgeNode(
        role=Role.EDGE1,
        run_id="sim00001",
        settings=settings,
        topics=topics,
        sensor=s1,
        steps=build_step_source("hw", settings.edge, settings.accel_steps),
        bus=bus1,
        clock=clock,
        actuator=ConsoleActuator(),
        calibration=JsonCalibrationStore(cal_path),
    )
    node2 = EdgeNode(
        role=Role.EDGE2,
        run_id="sim00002",
        settings=settings,
        topics=topics,
        sensor=s2,
        steps=build_step_source("hw", settings.edge, settings.accel_steps),
        bus=bus2,
        clock=clock,
        actuator=ConsoleActuator(),
        calibration=JsonCalibrationStore(cal_path),
    )

    for node, b in ((node1, bus1), (node2, bus2)):
        b.subscribe(topics.control, node._on_control)
        b.subscribe(topics.cues, node._on_cue)
        b.subscribe(topics.alerts, node._on_alert)
        b.connect(None)
        node._announce()

    eng_bus.publish(
        topics.control,
        codec.encode_command(codec.ControlCommand(codec.CommandName.START)),
    )

    for sec in range(spec.duration_s):
        node1.step()
        if spec.drop_edge2_at_s is None or sec < spec.drop_edge2_at_s:
            clock.advance(-settings.edge.window_s)
            node2.step()
        engine.tick()

    return records, tele_rows


def main() -> None:
    args = build_parser().parse_args()
    spec = SCENARIOS[args.scenario]
    records, tele_rows = run_scenario(spec, args.team_id, args.seed, args.config)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / f"{args.scenario}.jsonl"
    csv_path = out_dir / f"{args.scenario}.csv"

    jsonl_path.write_text(
        "\n".join(to_json_line(r) for r in records) + "\n", encoding="utf-8"
    )
    csv_path.write_text(telemetry_csv(tele_rows), encoding="utf-8")
    print(f"Skenario '{args.scenario}' ({spec.description}) selesai:")
    print(f"  - JSONL: {jsonl_path} ({len(records)} paket)")
    print(f"  - CSV  : {csv_path} ({len(tele_rows)} baris telemetry)")


if __name__ == "__main__":
    main()
