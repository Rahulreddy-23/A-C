# DHF-COMPONENT: COMP-03
# Implements: SRS-003, SRS-009, SRS-015, SRS-021, SRS-022, SRS-023, SRS-027, SRS-033
import math
from dataclasses import dataclass
from enum import StrEnum

from kestrel.alarm_latch import latched


def occluded(pressure: float, threshold: float = 80.0) -> bool:
    if pressure < 0:
        raise ValueError("Invalid pressure")
    return pressure > threshold


class PressureState(StrEnum):
    SAFE = "safe"
    OCCLUDED = "occluded"
    FAULT = "fault"


@dataclass(frozen=True)
class PressureSample:
    value_kpa: float
    timestamp_s: float


@dataclass(frozen=True)
class PressureDecision:
    state: PressureState
    stop_output: bool
    alarm_required: bool
    reason: str


class PressureMonitor:
    """Validate ordered samples and latch sustained threshold crossings.

    Time is supplied by the bench so boundary trials are deterministic.
    A missing or non-finite sample inhibits output; it never becomes a safe zero.
    """

    def __init__(self, threshold_kpa: float = 80.0, dwell_s: float = 3.0):
        if threshold_kpa <= 0 or dwell_s < 0:
            raise ValueError("Invalid pressure limits")
        self.threshold_kpa = threshold_kpa
        self.dwell_s = dwell_s
        self.last_time = None
        self.crossing_since = None
        self.latched = False

    def evaluate(self, sample: PressureSample | None) -> PressureDecision:
        if sample is None or not math.isfinite(sample.value_kpa):
            return PressureDecision(PressureState.FAULT, True, True, "Missing or invalid sample")
        if sample.value_kpa < 0 or not math.isfinite(sample.timestamp_s):
            return PressureDecision(
                PressureState.FAULT, True, True, "Invalid measured value or time"
            )
        if self.last_time is not None and sample.timestamp_s < self.last_time:
            return PressureDecision(PressureState.FAULT, True, True, "Decreasing sample timestamp")
        self.last_time = sample.timestamp_s
        if occluded(sample.value_kpa, self.threshold_kpa):
            if self.crossing_since is None:
                self.crossing_since = sample.timestamp_s
            if sample.timestamp_s - self.crossing_since >= self.dwell_s:
                self.latched = True
        else:
            self.crossing_since = None
        if self.latched:
            return PressureDecision(PressureState.OCCLUDED, True, True, "Sustained occlusion latch")
        return PressureDecision(PressureState.SAFE, False, False, "Valid sample below dwell limit")

    def acknowledge(self, sample: PressureSample) -> bool:
        if not math.isfinite(sample.value_kpa) or sample.value_kpa < 0:
            return False
        if occluded(sample.value_kpa, self.threshold_kpa):
            return False
        self.latched = False
        self.crossing_since = None
        return True


def pressure_alarm(decision: PressureDecision, active: bool, acknowledged: bool) -> bool:
    """Route a validated pressure decision through the shared alarm latch."""
    return latched(active, acknowledged, decision.alarm_required)
