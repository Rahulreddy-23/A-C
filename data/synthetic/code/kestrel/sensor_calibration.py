# DHF-COMPONENT: COMP-03
# Implements: SRS-003, SRS-009, SRS-015, SRS-021, SRS-022, SRS-023, SRS-027, SRS-033
def calibrated(reading: float, offset: float) -> float:
    return reading + offset


class Calibration:
    """Keep an explicit gain and offset; reject invalid service updates."""

    def __init__(self, gain: float = 1.0, offset: float = 0.0) -> None:
        import math

        if not math.isfinite(gain) or gain <= 0 or not math.isfinite(offset):
            raise ValueError("Invalid calibration")
        self.gain = gain
        self.offset = offset

    def apply(self, reading: float) -> float:
        import math

        if not math.isfinite(reading):
            raise ValueError("Invalid sensor reading")
        return calibrated(reading * self.gain, self.offset)

    def update(self, gain: float, offset: float, authorized: bool) -> None:
        if not authorized:
            raise PermissionError("Service authorization required")
        proposed = Calibration(gain, offset)
        self.gain, self.offset = proposed.gain, proposed.offset

    def snapshot(self) -> dict:
        return {"gain": self.gain, "offset": self.offset}
