# DHF-COMPONENT: COMP-04
# Implements: SRS-004, SRS-010, SRS-016, SRS-028
def highest(alarms: list[dict]) -> dict | None:
    return max(alarms, key=lambda a: a["priority"], default=None)


class PrioritySelector:
    """Keep stable alarm identities and select the highest active priority."""

    def __init__(self) -> None:
        self.events: dict[str, dict] = {}

    def update(self, code: str, priority: int, active: bool) -> None:
        if not code or priority not in (1, 2, 3):
            raise ValueError("Valid alarm code and priority required")
        self.events[code] = {"code": code, "priority": priority, "active": active}

    def select(self) -> dict | None:
        ordered = sorted(self.events.values(), key=lambda e: e["code"])
        selected = highest([e for e in ordered if e["active"]])
        return dict(selected) if selected else None

    def clear_inactive(self) -> None:
        self.events = {code: event for code, event in self.events.items() if event["active"]}

    def snapshot(self) -> list[dict]:
        return [dict(self.events[code]) for code in sorted(self.events)]

    def active_count(self) -> int:
        """Return the retained active-event count for the operator view."""
        return sum(event["active"] for event in self.events.values())
