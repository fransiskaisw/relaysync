"""Bus pesan dalam proses (tanpa jaringan) untuk skenario simulasi dan tes."""
from __future__ import annotations

import logging
from collections.abc import Callable

from relaysync.messaging.topics import topic_matches
from relaysync.ports import LastWill, MessageHandler

log = logging.getLogger(__name__)


class MemoryBroker:
    """Broker kecil: pengiriman sinkron, mendukung retained dan wildcard."""

    def __init__(self) -> None:
        self._retained: dict[str, bytes] = {}
        self._subs: list[tuple[str, MessageHandler]] = []

    def subscribe(self, topic_filter: str, handler: MessageHandler) -> None:
        self._subs.append((topic_filter, handler))
        for topic, payload in list(self._retained.items()):
            if topic_matches(topic_filter, topic):
                handler(topic, payload)

    def publish(self, topic: str, payload: bytes, retain: bool) -> None:
        if retain:
            self._retained[topic] = payload
        for topic_filter, handler in list(self._subs):
            if topic_matches(topic_filter, topic):
                handler(topic, payload)


class MemoryBus:
    def __init__(self, broker: MemoryBroker) -> None:
        self._broker = broker
        self._will: LastWill | None = None
        self._hooks: list[Callable[[], None]] = []

    def connect(self, will: LastWill | None) -> None:
        self._will = will
        for hook in self._hooks:
            hook()

    def disconnect(self) -> None:
        self._will = None

    def drop(self) -> None:
        """Simulasi putus tak wajar: broker mengirim Last Will."""
        if self._will is not None:
            self._broker.publish(self._will.topic, self._will.payload, self._will.retain)
            self._will = None

    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None:
        self._broker.publish(topic, payload, retain)

    def subscribe(self, topic_filter: str, handler: MessageHandler, *, qos: int = 1) -> None:
        self._broker.subscribe(topic_filter, handler)

    def add_connect_hook(self, hook: Callable[[], None]) -> None:
        self._hooks.append(hook)
