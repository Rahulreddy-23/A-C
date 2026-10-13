# DHF-COMPONENT: COMP-06
# Implements: SRS-027, SRS-029
def overdue(now: float, last: float, timeout: float) -> bool:
    return now - last > timeout


class Heartbeat:
    """Retain the last valid response time and expose deterministic timeout state."""

    def __init__(self, timeout_s: float) -> None:
        if timeout_s <= 0:
            raise ValueError("Positive timeout required")
        self.timeout_s = timeout_s
        self.last_response = None
        self.last_poll = None

    def response(self, now: float) -> None:
        if now < 0 or self.last_response is not None and now < self.last_response:
            raise ValueError("Invalid response timestamp")
        self.last_response = now

    def poll(self, now: float) -> bool:
        if now < 0 or self.last_poll is not None and now < self.last_poll:
            raise ValueError("Invalid polling clock")
        self.last_poll = now
        return self.last_response is None or overdue(now, self.last_response, self.timeout_s)

    def snapshot(self) -> dict:
        return {
            "timeout_s": self.timeout_s,
            "last_response": self.last_response,
            "last_poll": self.last_poll,
        }
