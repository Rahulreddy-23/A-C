# DHF-COMPONENT: COMP-03
# Implements: SRS-008, SRS-010
import math
from dataclasses import dataclass


def air_detected(reading: float, limit: float) -> bool:
    return reading > limit


@dataclass(frozen=True)
class AirDecision:
    stop_output: bool
    alarm_required: bool
    reason: str


class AirMonitor:
    """Treat a disconnected or non-finite air sensor as an unsafe fault."""

    def __init__(self, limit: float):
        if not math.isfinite(limit) or limit < 0:
            raise ValueError("Invalid air sensor limit")
        self.limit = limit
        self.latched = False

    def evaluate(self, reading: float | None, connected: bool = True) -> AirDecision:
        if not connected or reading is None or not math.isfinite(reading) or reading < 0:
            self.latched = True
            return AirDecision(True, True, "Air sensor fault")
        self.latched = self.latched or air_detected(reading, self.limit)
        return AirDecision(
            self.latched, self.latched, "Air latch" if self.latched else "Valid safe sample"
        )

    def acknowledge(self, reading: float, connected: bool = True) -> bool:
        if (
            not connected
            or not math.isfinite(reading)
            or reading < 0
            or air_detected(reading, self.limit)
        ):
            return False
        self.latched = False
        return True
