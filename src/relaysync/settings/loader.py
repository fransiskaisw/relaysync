"""Memuat YAML dan variabel lingkungan menjadi Settings yang tervalidasi."""
from __future__ import annotations

import os
from dataclasses import fields, is_dataclass, replace
from pathlib import Path
from typing import Any, get_args, get_origin, get_type_hints

import yaml

from .errors import ConfigError
from .identity import validate_team_id
from .models import Runtime, Settings

_ENV_KEYS = (
    "TEAM_ID",
    "PROJECT_ID",
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_TLS",
    "TIME_SCALE",
    "STEP_SENSOR",
    "ACCEL_SENSOR",
    "GYRO_SENSOR",
    "RELAYSYNC_CONFIG",
)
_TRUE_WORDS = {"1", "true", "yes", "ya"}
_FALSE_WORDS = {"0", "false", "no", "tidak"}


def read_env(env_file: str | Path = ".env") -> dict[str, str]:
    """Baca berkas .env sederhana; variabel lingkungan proses menang."""
    values: dict[str, str] = {}
    path = Path(env_file)
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    for key in _ENV_KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def find_config(explicit: str | None, env: dict[str, str]) -> Path:
    repo_default = Path(__file__).resolve().parents[3] / "configs" / "default.yaml"
    candidates = [explicit, env.get("RELAYSYNC_CONFIG"), "configs/default.yaml", repo_default]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise ConfigError("configs/default.yaml tidak ditemukan. Jalankan dari akar repo.")


def _convert(value: Any, hint: Any, path: str) -> Any:
    if is_dataclass(hint):
        return _build(hint, value, path)
    if get_origin(hint) is tuple:
        if not isinstance(value, list):
            raise ConfigError(f"{path}: harus berupa daftar")
        return tuple(_convert(item, get_args(hint)[0], path) for item in value)
    if hint is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"{path}: harus true atau false")
        return value
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{path}: harus bilangan bulat")
        return value
    if hint is float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"{path}: harus angka")
        return float(value)
    if hint is str:
        if not isinstance(value, str):
            raise ConfigError(f"{path}: harus teks")
        return value
    raise ConfigError(f"{path}: tipe {hint} tidak didukung")


def _build(cls: Any, data: Any, path: str) -> Any:
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: harus berupa objek")
    hints = get_type_hints(cls)
    names = {f.name for f in fields(cls)}
    unknown, missing = set(data) - names, names - set(data)
    if unknown or missing:
        raise ConfigError(f"{path}: kunci tak dikenal {sorted(unknown)}, kurang {sorted(missing)}")
    return cls(**{n: _convert(data[n], hints[n], f"{path}.{n}") for n in names})


def validate(s: Settings) -> None:
    """Periksa rentang dan urutan logis ambang; lempar ConfigError bila janggal."""
    e, f, t, r, c, g = s.edge, s.fusion, s.track, s.readiness, s.cue, s.engine
    lengths = (e.step_lengths.edge1_m, e.step_lengths.edge2_m)
    checks = [
        (e.window_s > 0, "edge.window_s harus > 0"),
        (e.cadence_window_s >= e.window_s, "edge.cadence_window_s >= edge.window_s"),
        (e.step_len_min_m < e.step_len_max_m, "step_len_min_m < step_len_max_m"),
        (all(e.step_len_min_m <= v <= e.step_len_max_m for v in lengths),
         "panjang langkah default harus di dalam rentang min dan max"),
        (bool(e.step_sensor.strip() and e.accel_sensor.strip() and e.gyro_sensor.strip()),
         "nama sensor tidak boleh kosong"),
        (0 < s.accel_steps.smooth_alpha <= 1, "accel_steps.smooth_alpha di antara 0 dan 1"),
        (r.walk_cadence_spm < r.run_cadence_spm, "walk_cadence_spm < run_cadence_spm"),
        (0 <= r.hysteresis_spm < r.run_cadence_spm, "hysteresis_spm harus < run_cadence_spm"),
        (s.speed.window_s > 0, "speed.window_s harus > 0"),
        (g.leg_min_m <= t.leg_length_m <= g.leg_max_m, "track.leg_length_m di luar rentang engine"),
        (g.zone_min_m <= t.zone_length_m <= g.zone_max_m, "track.zone_length_m di luar rentang engine"),
        (t.entry_margin_m >= 0, "track.entry_margin_m harus >= 0"),
        (f.gap_opt_min_m < f.gap_opt_max_m < f.gap_far_m, "gap_opt_min_m < gap_opt_max_m < gap_far_m"),
        (f.gap_opt_min_m <= f.pass_gap_m <= f.gap_opt_max_m, "pass_gap_m harus di dalam zona gap optimal"),
        (f.speed_match_tol_mps > 0, "speed_match_tol_mps harus > 0"),
        (min(f.hold_s, f.clear_s, f.stall_s, f.pass_hold_s, f.optimal_exit_s) >= 0,
         "durasi hold/clear/stall/pass/optimal_exit harus >= 0"),
        (f.data_gap_s > 0, "fusion.data_gap_s harus > 0"),
        (c.go_trigger_m > 0 and c.go_cue_eta_s > 0, "go_trigger_m dan go_cue_eta_s harus > 0"),
        (min(c.cue_cooldown_s, c.alert_cooldown_s) > 0, "cooldown harus > 0"),
        (c.alert_pulses >= 1, "cue.alert_pulses harus >= 1"),
        (g.calibrate_min_m <= g.calibrate_default_m <= g.calibrate_max_m,
         "engine.calibrate_default_m di luar rentang"),
        (g.max_clock_skew_s > 0, "engine.max_clock_skew_s harus > 0"),
    ]
    for ok, message in checks:
        if not ok:
            raise ConfigError(message)


def _apply_overrides(settings: Settings, env: dict[str, str]) -> Settings:
    broker = settings.broker
    edge = settings.edge
    engine = settings.engine
    try:
        if "MQTT_HOST" in env and env["MQTT_HOST"]:
            broker = replace(broker, host=env["MQTT_HOST"])
        if "MQTT_PORT" in env and env["MQTT_PORT"]:
            broker = replace(broker, port=int(env["MQTT_PORT"]))
        if "MQTT_TLS" in env and env["MQTT_TLS"]:
            word = env["MQTT_TLS"].lower()
            if word not in _TRUE_WORDS | _FALSE_WORDS:
                raise ConfigError("MQTT_TLS harus true atau false")
            broker = replace(broker, tls=word in _TRUE_WORDS)
        if "STEP_SENSOR" in env and env["STEP_SENSOR"]:
            edge = replace(edge, step_sensor=env["STEP_SENSOR"])
        if "ACCEL_SENSOR" in env and env["ACCEL_SENSOR"]:
            edge = replace(edge, accel_sensor=env["ACCEL_SENSOR"])
        if "GYRO_SENSOR" in env and env["GYRO_SENSOR"]:
            edge = replace(edge, gyro_sensor=env["GYRO_SENSOR"])
        if "TIME_SCALE" in env and env["TIME_SCALE"]:
            scale = float(env["TIME_SCALE"])
            if scale <= 0:
                raise ConfigError("TIME_SCALE harus > 0")
            edge = replace(edge, window_s=edge.window_s / scale)
            engine = replace(engine, tick_s=engine.tick_s / scale)
    except ValueError as exc:
        raise ConfigError(f"Nilai .env tidak valid: {exc}") from exc
    return replace(settings, broker=broker, edge=edge, engine=engine)


def load_settings(config_path: str | None = None, env: dict[str, str] | None = None) -> Settings:
    env = env if env is not None else read_env()
    path = find_config(config_path, env)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    settings = _apply_overrides(_build(Settings, raw, "config"), env)
    validate(settings)
    return settings


def load_runtime(config_path: str | None = None, env_file: str = ".env") -> Runtime:
    """Muat konfigurasi dan TEAM_ID (atau alias PROJECT_ID); menolak placeholder."""
    env = read_env(env_file)
    settings = load_settings(config_path, env)
    raw_id = env.get("TEAM_ID") or env.get("PROJECT_ID")
    return Runtime(settings=settings, team_id=validate_team_id(raw_id))
