# DHF-COMPONENT: COMP-02
# Implements: SRS-002, SRS-028
def target_reached(delivered: float, target: float) -> bool:
    return delivered >= target


class VolumeAccumulator:
    """Clamp each increment to remaining target and preserve volume on stop."""

    def __init__(self, target: float) -> None:
        if target <= 0:
            raise ValueError("Positive target required")
        self.target = target
        self.delivered = 0.0
        self.stopped = False

    def add(self, requested: float) -> float:
        if requested < 0:
            raise ValueError("Negative delivery increment")
        if self.stopped:
            return 0.0
        actual = min(requested, max(0.0, self.target - self.delivered))
        self.delivered += actual
        self.stopped = target_reached(self.delivered, self.target)
        return actual

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> dict:
        return {"target": self.target, "delivered": self.delivered, "stopped": self.stopped}
