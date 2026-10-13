# DHF-COMPONENT: COMP-04
# Implements: SRS-012, SRS-013
from dataclasses import dataclass
from enum import IntEnum


def latched(active: bool, acknowledged: bool, unsafe: bool) -> bool:
    return unsafe or (active and not acknowledged)


class Priority(IntEnum):
    ADVISORY = 1
    WARNING = 2
    CRITICAL = 3


@dataclass
class AlarmState:
    code: str
    priority: Priority
    unsafe: bool = False
    active: bool = False
    acknowledged: bool = False


class AlarmRegistry:
    """Keep critical fault latches independent of the operator display.

    Acknowledgement is an event, not proof that the unsafe condition ended.
    """

    def __init__(self) -> None:
        self.alarms: dict[str, AlarmState] = {}
        self.events: list[dict] = []

    def update(self, code: str, priority: Priority, unsafe: bool) -> AlarmState:
        if not code:
            raise ValueError("Alarm code required")
        alarm = self.alarms.setdefault(code, AlarmState(code, priority))
        alarm.priority = priority
        alarm.unsafe = unsafe
        alarm.active = latched(alarm.active, alarm.acknowledged, unsafe)
        if unsafe:
            alarm.acknowledged = False
        self.events.append({"code": code, "unsafe": unsafe, "active": alarm.active})
        return alarm

    def acknowledge(self, code: str) -> bool:
        if code not in self.alarms:
            raise KeyError(code)
        alarm = self.alarms[code]
        alarm.acknowledged = True
        alarm.active = latched(alarm.active, True, alarm.unsafe)
        self.events.append({"code": code, "acknowledged": True, "active": alarm.active})
        return not alarm.active

    def stop_required(self) -> bool:
        return any(a.active and a.priority == Priority.CRITICAL for a in self.alarms.values())

    def visible(self) -> list[AlarmState]:
        return sorted(
            (a for a in self.alarms.values() if a.active), key=lambda a: (-a.priority, a.code)
        )
