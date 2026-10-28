"""Node edge: sensor -> langkah -> fitur (Processing 1 dan 2) -> telemetry; menjalankan
aktuator saat cue atau alert datang."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from relaysync.domain.cadence import CadenceCounter
from relaysync.domain.distance import CalibrationError, estimate_distance_m, step_length_from_run
from relaysync.domain.models import (
    AlertKind,
    Readiness,
    Role,
    SensorBatch,
    StepsSource,
    Telemetry,
    WindowFeatures,
)
from relaysync.domain.readiness import (
    ReadinessClassifier,
    ReadinessRules,
    accel_dev_rms,
    gyro_path_rad,
)
from relaysync.domain.states import ALERT_TEXT
from relaysync.messaging import codec
from relaysync.messaging.errors import PayloadError
from relaysync.messaging.topics import TopicMap
from relaysync.ports import (
    Actuator,
    CalibrationStore,
    Clock,
    LastWill,
    MessageBus,
    SensorReader,
    StepSource,
)
from relaysync.settings.models import Settings

log = logging.getLogger(__name__)

PRESENCE_ONLINE = b"online"
PRESENCE_OFFLINE = b"offline"
NOTIFICATION_ID = "relaysync-signal"
NOTIFICATION_TITLE = "RelaySync"
GO_TEXT = "GO! Mulai berlari sekarang."
_REBASE_COMMANDS = {codec.CommandName.START, codec.CommandName.RESET,
                    codec.CommandName.NEW_ATTEMPT}


@dataclass(frozen=True, slots=True)
class _CalibrationRun:
    distance_m: float
    start_steps: int


class EdgeNode:
    def __init__(self, *, role: Role, run_id: str, settings: Settings, topics: TopicMap,
                 sensor: SensorReader, steps: StepSource, bus: MessageBus, clock: Clock,
                 actuator: Actuator, calibration: CalibrationStore) -> None:
        self._role = role
        self._run_id = run_id
        self._cfg = settings
        self._topics = topics
        self._sensor, self._steps = sensor, steps
        self._bus, self._clock, self._actuator = bus, clock, actuator
        self._store = calibration
        self._limits = codec.limits_from_settings(settings)
        self._cadence = CadenceCounter(settings.edge.cadence_window_s)
        r = settings.readiness
        self._readiness = ReadinessClassifier(ReadinessRules(
            r.stationary_dev_max, r.walk_cadence_spm, r.run_cadence_spm, r.run_hold_s,
            r.hysteresis_spm, r.turn_gyro_path_rad))
        self._lock = threading.Lock()
        self._n_msg = 0
        self._last_total = 0
        self._pending: _CalibrationRun | None = None
        self._step_len_m, self._calibrated = self._initial_step_length()

    def _initial_step_length(self) -> tuple[float, bool]:
        edge = self._cfg.edge
        default = (edge.step_lengths.edge1_m if self._role is Role.EDGE1
                   else edge.step_lengths.edge2_m)
        saved = self._store.load(self._role)
        if saved is not None and edge.step_len_min_m <= saved <= edge.step_len_max_m:
            return saved, True
        return default, False

    # ------------------------------------------------------------- lifecycle
    def run(self, stop: threading.Event) -> None:
        self._bus.add_connect_hook(self._announce)
        self._bus.subscribe(self._topics.control, self._on_control)
        self._bus.subscribe(self._topics.cues, self._on_cue)
        self._bus.subscribe(self._topics.alerts, self._on_alert)
        self._bus.connect(LastWill(self._topics.presence(self._role), PRESENCE_OFFLINE))
        log.info("Edge %s berjalan (run %s, panjang langkah %.2f m, kalibrasi=%s)",
                 self._role.value, self._run_id, self._step_len_m, self._calibrated)
        try:
            while not stop.is_set():
                self.step()
        finally:
            self._shutdown()

    def step(self) -> None:
        """Satu jendela: baca sensor, hitung fitur, kirim telemetry."""
        batch = self._sensor.read_batch(self._cfg.edge.window_s)
        with self._lock:
            features = self._compute(batch)
        self._n_msg += 1
        telemetry = Telemetry(self._role, self._run_id, self._n_msg, self._clock.now_ms(), features)
        self._bus.publish(self._topics.telemetry(self._role), codec.encode_telemetry(telemetry))

    # ------------------------------------------------------------ processing
    def _compute(self, batch: SensorBatch) -> WindowFeatures:
        total = self._steps.update(batch)
        self._last_total = total
        self._cadence.record(self._clock.monotonic_s(), total)
        cadence = self._cadence.cadence_spm()
        dev = accel_dev_rms(batch.accel)
        gyro: float | None = None
        ready: Readiness | None = None
        if self._role is Role.EDGE2:
            gyro = gyro_path_rad(batch.gyro, self._cfg.edge.max_gyro_dt_s)
            ready = self._readiness.update(dev, cadence, gyro, batch.duration_s)
        return WindowFeatures(
            window_s=batch.duration_s, steps_total=total,
            dist_est_m=estimate_distance_m(total, self._step_len_m), step_len_m=self._step_len_m,
            cadence_spm=cadence, accel_dev_rms=dev, steps_src=StepsSource(self._steps.name),
            calibrated=self._calibrated, gyro_path_rad=gyro, readiness=ready)

    # -------------------------------------------------------------- presence
    def _announce(self) -> None:
        self._bus.publish(self._topics.presence(self._role), PRESENCE_ONLINE, retain=True)

    def _shutdown(self) -> None:
        self._bus.publish(self._topics.presence(self._role), PRESENCE_OFFLINE, retain=True)
        self._actuator.cancel_vibration()
        self._bus.disconnect()
        self._sensor.close()

    # -------------------------------------------------------------- handlers
    def _on_control(self, _topic: str, payload: bytes) -> None:
        try:
            command = codec.decode_command(payload, self._limits)
        except PayloadError as exc:
            log.warning("Perintah ditolak: %s", exc)
            return
        with self._lock:
            if command.name in _REBASE_COMMANDS:
                self._rebase()
            elif command.name is codec.CommandName.CALIBRATE_STEP and command.target is self._role:
                self._toggle_calibration(command.distance_m or self._limits.calibrate_default_m)

    def _rebase(self) -> None:
        self._steps.rebase()
        self._cadence.clear()
        self._readiness.reset()
        self._last_total = 0
        if self._pending is not None:
            log.warning("Kalibrasi dibatalkan karena sesi di-reset.")
            self._pending = None

    def _toggle_calibration(self, distance_m: float) -> None:
        """Panggilan pertama memulai, panggilan kedua menyelesaikan kalibrasi."""
        if self._pending is None:
            self._pending = _CalibrationRun(distance_m, self._last_total)
            log.info("Kalibrasi dimulai: tempuh %.0f m dengan langkah biasa, lalu kirim "
                     "calibrate_step lagi.", distance_m)
            return
        run, self._pending = self._pending, None
        edge = self._cfg.edge
        try:
            length = step_length_from_run(run.distance_m, self._last_total - run.start_steps,
                                          edge.step_len_min_m, edge.step_len_max_m)
        except CalibrationError as exc:
            log.warning("Kalibrasi ditolak: %s", exc)
            return
        self._step_len_m, self._calibrated = length, True
        self._store.save(self._role, length)
        log.info("Kalibrasi selesai: panjang langkah %.3f m (disimpan)", length)

    def _on_cue(self, _topic: str, payload: bytes) -> None:
        try:
            codec.decode_cue(payload)
        except PayloadError as exc:
            log.warning("Cue ditolak: %s", exc)
            return
        if self._role is Role.EDGE2:
            self._actuator.vibrate((self._cfg.cue.vibrate_cue_ms,), 0)
            self._actuator.notify(NOTIFICATION_TITLE, GO_TEXT, NOTIFICATION_ID)

    def _on_alert(self, _topic: str, payload: bytes) -> None:
        try:
            message = codec.decode_alert(payload)
        except PayloadError as exc:
            log.warning("Alert ditolak: %s", exc)
            return
        if message.event is AlertKind.CLEARED:
            self._actuator.cancel_vibration()
            self._actuator.clear_notification(NOTIFICATION_ID)
            return
        cue = self._cfg.cue
        self._actuator.vibrate((cue.vibrate_alert_ms,) * cue.alert_pulses, cue.alert_pause_ms)
        self._actuator.notify(NOTIFICATION_TITLE, ALERT_TEXT[message.reason], NOTIFICATION_ID)
