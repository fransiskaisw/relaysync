"""Pemetaan topic MQTT: relaysync/<TEAM_ID>/..."""
from __future__ import annotations

from dataclasses import dataclass

from relaysync.domain.models import Role

from .errors import TopicError

ROOT_PREFIX = "relaysync"
KIND_TELEMETRY = "telemetry"
KIND_PRESENCE = "presence"


@dataclass(frozen=True, slots=True)
class TopicMap:
    team_id: str

    @property
    def root(self) -> str:
        return f"{ROOT_PREFIX}/{self.team_id}"

    def telemetry(self, role: Role) -> str:
        return f"{self.root}/edge/{role.value}/{KIND_TELEMETRY}"

    def presence(self, role: Role) -> str:
        return f"{self.root}/edge/{role.value}/{KIND_PRESENCE}"

    @property
    def session(self) -> str:
        return f"{self.root}/session"

    @property
    def alerts(self) -> str:
        return f"{self.root}/alerts"

    @property
    def cues(self) -> str:
        return f"{self.root}/cues"

    @property
    def events(self) -> str:
        return f"{self.root}/events"

    @property
    def control(self) -> str:
        return f"{self.root}/control"

    def all_topics(self) -> tuple[str, ...]:
        edge = [f(r) for r in Role for f in (self.telemetry, self.presence)]
        return (*edge, self.session, self.alerts, self.cues, self.events, self.control)

    def parse_edge(self, topic: str) -> tuple[Role, str]:
        """Pecah topic edge menjadi (peran, jenis)."""
        prefix = f"{self.root}/edge/"
        if not topic.startswith(prefix):
            raise TopicError(f"topic bukan milik tim ini: {topic}")
        parts = topic[len(prefix):].split("/")
        if len(parts) != 2 or parts[1] not in (KIND_TELEMETRY, KIND_PRESENCE):
            raise TopicError(f"topic edge tidak dikenal: {topic}")
        try:
            return Role(parts[0]), parts[1]
        except ValueError as exc:
            raise TopicError(f"peran tidak dikenal: {parts[0]}") from exc


def split_topic(topic: str) -> str:
    """Bagian topic setelah relaysync/<TEAM_ID>/ (untuk pembaca generik)."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != ROOT_PREFIX:
        raise TopicError(f"bukan topic RelaySync: {topic}")
    return "/".join(parts[2:])


def topic_matches(topic_filter: str, topic: str) -> bool:
    """Pencocokan filter MQTT dengan wildcard '+' dan '#'."""
    f_parts, t_parts = topic_filter.split("/"), topic.split("/")
    for index, part in enumerate(f_parts):
        if part == "#":
            return True
        if index >= len(t_parts) or (part != "+" and part != t_parts[index]):
            return False
    return len(f_parts) == len(t_parts)
