# DHF-COMPONENT: COMP-06
# Implements: SRS-026
def valid_frame(payload: bytes) -> bool:
    return payload.startswith(b"KIC:") and payload.endswith(b"\n")


class FrameBuffer:
    """Bound retained bytes and expose complete validated synthetic frames."""

    def __init__(self, maximum_bytes: int = 1024) -> None:
        if maximum_bytes < 5:
            raise ValueError("Frame limit too small")
        self.maximum_bytes = maximum_bytes
        self.buffer = bytearray()

    def append(self, chunk: bytes) -> list[bytes]:
        if len(self.buffer) + len(chunk) > self.maximum_bytes:
            self.buffer.clear()
            raise ValueError("Frame exceeds configured limit")
        self.buffer.extend(chunk)
        frames = []
        while b"\n" in self.buffer:
            line, _, remaining = self.buffer.partition(b"\n")
            frame = bytes(line) + b"\n"
            self.buffer = bytearray(remaining)
            if not valid_frame(frame):
                raise ValueError("Invalid message frame")
            frames.append(frame)
        return frames

    def reset(self) -> None:
        """Discard incomplete input after a transport fault."""
        self.buffer.clear()
