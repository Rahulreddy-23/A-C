# DHF-COMPONENT: COMP-04
# Implements: SRS-014
def audible(critical: bool, muted: bool) -> bool:
    return critical and not muted


class AlertScheduler:
    """Bound mute duration while scheduling repeated critical bench alerts."""

    def __init__(self, interval_s: float, maximum_mute_s: float) -> None:
        if interval_s <= 0 or maximum_mute_s < 0:
            raise ValueError("Invalid alert schedule")
        self.interval_s = interval_s
        self.maximum_mute_s = maximum_mute_s
        self.mute_until = 0.0
        self.last_pulse = None

    def mute(self, now: float, requested_s: float) -> None:
        if now < 0 or requested_s < 0:
            raise ValueError("Invalid mute request")
        self.mute_until = now + min(requested_s, self.maximum_mute_s)

    def tick(self, now: float, critical: bool) -> bool:
        if now < 0 or self.last_pulse is not None and now < self.last_pulse:
            raise ValueError("Invalid alert clock")
        if not audible(critical, now < self.mute_until):
            return False
        due = self.last_pulse is None or now - self.last_pulse >= self.interval_s
        if due:
            self.last_pulse = now
        return due
