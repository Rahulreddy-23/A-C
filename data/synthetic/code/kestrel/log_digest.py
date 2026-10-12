# DHF-COMPONENT: COMP-06
# Implements: SRS-006, SRS-012, SRS-018, SRS-024, SRS-030
import hashlib


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class IntegrityRecord:
    """Retain an immutable digest and verify subsequently exported bytes."""

    def __init__(self, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("Binary evidence payload required")
        self.expected = digest(payload)
        self.size = len(payload)

    def verify(self, candidate: bytes) -> bool:
        import hmac

        if not isinstance(candidate, bytes) or len(candidate) != self.size:
            return False
        return hmac.compare_digest(self.expected, digest(candidate))

    def describe(self) -> dict:
        return {"algorithm": "sha256", "size_bytes": self.size, "content_hash": self.expected}

    def require_valid(self, candidate: bytes) -> None:
        if not self.verify(candidate):
            raise ValueError("Evidence integrity mismatch")
