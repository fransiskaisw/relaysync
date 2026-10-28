"""Bus pesan MQTT berbasis paho-mqtt 2.x: TLS, reconnect otomatis, Last Will."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

import certifi
import paho.mqtt.client as mqtt

from relaysync.ports import LastWill, MessageHandler
from relaysync.settings.models import BrokerSettings

log = logging.getLogger(__name__)

RECONNECT_MIN_S = 1
RECONNECT_MAX_S = 30
MAX_QUEUED = 100
FLUSH_TIMEOUT_S = 2.0


class MqttBus:
    def __init__(self, settings: BrokerSettings, client_id: str) -> None:
        self._settings = settings
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv311
        )
        if settings.tls:
            self._client.tls_set(ca_certs=certifi.where())
        self._client.reconnect_delay_set(RECONNECT_MIN_S, RECONNECT_MAX_S)
        self._client.max_queued_messages_set(MAX_QUEUED)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._subs: dict[str, int] = {}
        self._hooks: list[Callable[[], None]] = []
        self._connected = threading.Event()
        self._last_info: mqtt.MQTTMessageInfo | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def wait_connected(self, timeout_s: float) -> bool:
        return self._connected.wait(timeout_s)

    def connect(self, will: LastWill | None) -> None:
        """Non-blokir: koneksi dan reconnect berjalan di thread latar paho."""
        if will is not None:
            self._client.will_set(will.topic, will.payload, qos=1, retain=will.retain)
        self._client.connect_async(
            self._settings.host, self._settings.port, self._settings.keepalive_s
        )
        self._client.loop_start()

    def disconnect(self) -> None:
        if self._last_info is not None:
            try:
                self._last_info.wait_for_publish(FLUSH_TIMEOUT_S)
            except (RuntimeError, ValueError):
                log.debug("pesan terakhir tidak sempat terkirim")
        self._client.disconnect()
        self._client.loop_stop()

    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None:
        info = self._client.publish(topic, payload, qos=qos, retain=retain)
        self._last_info = info
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            log.debug("publish %s tertunda atau gagal (rc=%s)", topic, info.rc)

    def subscribe(self, topic_filter: str, handler: MessageHandler, *, qos: int = 1) -> None:
        def dispatch(_client: Any, _userdata: Any, message: mqtt.MQTTMessage) -> None:
            try:
                handler(message.topic, bytes(message.payload))
            except Exception:  # noqa: BLE001 - thread paho tidak boleh mati karena satu pesan
                log.exception("handler gagal untuk topic %s", message.topic)

        self._client.message_callback_add(topic_filter, dispatch)
        self._subs[topic_filter] = qos
        if self.is_connected:
            self._client.subscribe(topic_filter, qos)

    def add_connect_hook(self, hook: Callable[[], None]) -> None:
        self._hooks.append(hook)

    def _on_connect(self, client: Any, _userdata: Any, _flags: Any, reason_code: Any,
                    _properties: Any) -> None:
        if reason_code.is_failure:
            log.error("Koneksi MQTT ditolak: %s", reason_code)
            return
        log.info("Terhubung ke %s:%d", self._settings.host, self._settings.port)
        for topic_filter, qos in self._subs.items():
            client.subscribe(topic_filter, qos)
        self._connected.set()
        for hook in self._hooks:
            hook()

    def _on_disconnect(self, _client: Any, _userdata: Any, _flags: Any, reason_code: Any,
                       _properties: Any) -> None:
        self._connected.clear()
        log.warning("Koneksi MQTT terputus (%s), mencoba lagi otomatis", reason_code)
