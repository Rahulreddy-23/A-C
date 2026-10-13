from typing import Any


class MockAdapter:
    """Deterministic fixture prose: not a substitute for a live quality check."""

    def complete(self, model: str, prompt: str, pack: dict[str, Any], limit: int) -> dict:
        evidence = pack.get("evidence", [])
        kind = pack.get("preferred_kind", "sourced")
        if "failed_results" in pack.get("facts", {}):
            rows = pack["facts"]["rows"]
            ids = {a["id"] for a in evidence}
            return {
                "claims": [
                    {
                        "text": (
                            f"{row['result']} records {row['outcome'].lower()} "
                            f"execution of {row['case']}."
                        ),
                        "kind": kind,
                        "citations": [row["result"], row["case"]],
                        "confidence": 1.0,
                    }
                    for row in rows
                    if row["result"] in ids and row["case"] in ids
                ]
            }
        return {
            "claims": [
                {
                    "text": (
                        f"{item['title']} is implemented in {item['properties']['Path']}."
                        if item["id"].startswith("UNIT-") and "Path" in item.get("properties", {})
                        else item["body"]
                    ),
                    "kind": kind,
                    "citations": [item["id"]],
                    "confidence": 1.0,
                }
                for item in evidence[:3]
                if item.get("body")
            ]
        }
