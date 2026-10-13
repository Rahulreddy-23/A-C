# DHF-COMPONENT: COMP-02
# Implements: SRS-006
def pulse_interval(rate: float, pulses_per_ml: int) -> float:
    if rate <= 0 or pulses_per_ml <= 0:
        raise ValueError("Positive rate and calibration required")
    return 3600.0 / (rate * pulses_per_ml)


class MotorSchedule:
    """Compute bounded bench pulse schedules from validated calibration.

    This fixture reports requested pulses; it never drives a physical motor.
    """

    def __init__(self, pulses_per_ml: int) -> None:
        if pulses_per_ml <= 0:
            raise ValueError("Positive calibration required")
        self.pulses_per_ml = pulses_per_ml
        self.rate = 0.0
        self.pending = 0.0

    def configure(self, rate: float) -> None:
        pulse_interval(rate, self.pulses_per_ml)
        self.rate = rate

    def pulses(self, elapsed_s: float, enabled: bool) -> int:
        if elapsed_s < 0:
            raise ValueError("Negative elapsed time")
        if not enabled or self.rate <= 0:
            self.pending = 0.0
            return 0
        self.pending += self.rate * self.pulses_per_ml * elapsed_s / 3600.0
        count = int(self.pending)
        self.pending -= count
        return count
