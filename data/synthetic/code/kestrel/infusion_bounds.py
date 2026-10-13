# DHF-COMPONENT: COMP-02
# Implements: SRS-001, SRS-003, SRS-004, SRS-005, SRS-030
import math
from dataclasses import dataclass
from enum import StrEnum


def within_bounds(rate: float, minimum: float, maximum: float) -> bool:
    return minimum <= rate <= maximum


class DeliveryMode(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    FAULT = "fault"


@dataclass(frozen=True)
class DeliveryConfiguration:
    rate_ml_h: float
    target_ml: float
    maximum_rate_ml_h: float

    def validate(self) -> None:
        values = (self.rate_ml_h, self.target_ml, self.maximum_rate_ml_h)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Non-finite configuration")
        if self.target_ml <= 0 or not within_bounds(self.rate_ml_h, 0.01, self.maximum_rate_ml_h):
            raise ValueError("Delivery configuration outside bounds")


class DeliveryController:
    """Apply validated configuration atomically; inhibit output on any fault."""

    def __init__(self) -> None:
        self.configuration: DeliveryConfiguration | None = None
        self.mode = DeliveryMode.STOPPED
        self.delivered_ml = 0.0
        self.events: list[str] = []

    def configure(self, proposed: DeliveryConfiguration) -> None:
        if self.mode == DeliveryMode.RUNNING:
            raise RuntimeError("Pause before changing configuration")
        proposed.validate()
        self.configuration = proposed
        self.events.append("configuration accepted")

    def start(self, sensor_safe: bool, alarm_active: bool) -> None:
        if self.configuration is None:
            raise RuntimeError("Validated configuration required")
        self.configuration.validate()
        if not sensor_safe or alarm_active:
            self.mode = DeliveryMode.FAULT
            self.events.append("start inhibited")
            return
        self.mode = DeliveryMode.RUNNING
        self.events.append("delivery started")

    def tick(self, elapsed_s: float, sensor_safe: bool) -> float:
        if elapsed_s < 0 or not math.isfinite(elapsed_s):
            self.mode = DeliveryMode.FAULT
            raise ValueError("Invalid elapsed time")
        if not sensor_safe:
            self.mode = DeliveryMode.FAULT
        if self.mode != DeliveryMode.RUNNING or self.configuration is None:
            return 0.0
        increment = self.configuration.rate_ml_h * elapsed_s / 3600.0
        remaining = max(0.0, self.configuration.target_ml - self.delivered_ml)
        delivered = min(increment, remaining)
        self.delivered_ml += delivered
        if self.delivered_ml >= self.configuration.target_ml:
            self.mode = DeliveryMode.STOPPED
            self.events.append("target reached")
        return delivered

    def pause(self) -> None:
        if self.mode == DeliveryMode.RUNNING:
            self.mode = DeliveryMode.PAUSED
            self.events.append("delivery paused")

    def stop(self) -> None:
        self.mode = DeliveryMode.STOPPED
        self.events.append("delivery stopped")
