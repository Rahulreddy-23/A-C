# DHF-COMPONENT: COMP-06
# Implements: SRS-024, SRS-031, SRS-033
import hashlib
import json
from dataclasses import asdict, dataclass


def append_event(events: list[dict], event: dict) -> list[dict]:
    if events and event["time"] < events[-1]["time"]:
        raise ValueError("Decreasing timestamp")
    return [*events, dict(event)]


@dataclass(frozen=True)
class AuditEvent:
    time: float
    code: str
    details: dict


class EventRecorder:
    """Append ordered records and expose a digest for synthetic audit trials."""

    def __init__(self) -> None:
        self.events: list[dict] = []

    def record(self, event: AuditEvent) -> None:
        if not event.code:
            raise ValueError("Event code required")
        encoded = asdict(event)
        self.events = append_event(self.events, encoded)

    def export(self) -> list[dict]:
        return json.loads(json.dumps(self.events))

    def content_digest(self) -> str:
        data = json.dumps(self.events, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(data).hexdigest()
