# DHF-COMPONENT: COMP-03
# Implements: SRS-022
import math
from collections import deque


def average(samples: list[float]) -> float:
    if not samples:
        raise ValueError("No samples")
    return sum(samples) / len(samples)


class PressureWindow:
    """Bound retained samples and reject invalid values before changing the window."""

    def __init__(self, size: int):
        if size <= 0:
            raise ValueError("Positive window size required")
        self.samples: deque[float] = deque(maxlen=size)
        self.total_samples = 0

    def append(self, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("Invalid pressure sample")
        self.samples.append(value)
        self.total_samples += 1
        return average(list(self.samples))

    def reset(self) -> None:
        self.samples.clear()
        self.total_samples = 0

    def snapshot(self) -> dict:
        return {
            "size": self.samples.maxlen,
            "samples": list(self.samples),
            "total_samples": self.total_samples,
        }
