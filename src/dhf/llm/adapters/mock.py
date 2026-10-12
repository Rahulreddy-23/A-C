from typing import Any


class MockAdapter:
    """Deterministic fixture prose: not a substitute for a live quality check."""

    def complete(self, model: str, prompt: str, pack: dict[str, Any], limit: int) -> dict:
        evidence = pack.get("evidence", [])
        kind = pack.get("preferred_kind", "sourced")
        return {
            "claims": [
                {"text": item["body"], "kind": kind, "citations": [item["id"]], "confidence": 1.0}
                for item in evidence[:3]
                if item.get("body")
            ]
        }
