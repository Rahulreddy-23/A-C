from typing import Any


class MockAdapter:
    """Deterministic fixture prose: not a substitute for a live quality check."""

    def complete(self, model: str, prompt: str, pack: dict[str, Any], limit: int) -> dict:
        evidence = pack.get("evidence", [])
        kind = pack.get("preferred_kind", "sourced")
        if pack.get("facts", {}).get("review_drafting"):
            from pathlib import Path

            import yaml

            template = yaml.safe_load(Path("specs/mock/review.yaml").read_text())[
                pack["facts"]["review_drafting"]
            ]
            ids = {a["id"] for a in evidence}
            return {
                "claims": [
                    {
                        "text": template.format(**finding),
                        "kind": "suggested",
                        "citations": [finding["artifact_id"]],
                        "confidence": 0.5,
                    }
                    for finding in pack["facts"]["gap_findings"]
                    if finding["artifact_id"] in ids
                ][: pack.get("max_claims", 3)]
            }
        if pack.get("facts", {}).get("proposal_rule"):
            from pathlib import Path

            import yaml

            rule = pack["facts"]["proposal_rule"]
            if rule == "L03":
                return {"claims": []}
            text = yaml.safe_load(Path("specs/mock/proposals.yaml").read_text())[rule]
            return {
                "claims": [
                    {
                        "text": text.format(subject=pack["facts"]["subject"]),
                        "kind": "suggested",
                        "citations": [pack["facts"]["subject"]],
                        "confidence": 0.5,
                    }
                ]
            }
        if pack.get("facts", {}).get("risk_authoring"):
            hazard = next(a for a in evidence if a["id"] == pack["facts"]["hazard"])
            body = hazard["body"]
            cause = body.split("Cause sequence: ", 1)[1].split(". ", 1)[0]
            harm = body.split("Foreseeable harm: ", 1)[1].split(". ", 1)[0]
            drafts = [
                hazard["title"],
                cause,
                cause,
                harm,
                "Review recorded controls and verification before accepting this analysis.",
            ]
            return {
                "claims": [
                    {
                        "text": label + ": " + text,
                        "kind": "suggested",
                        "citations": [hazard["id"]],
                        "confidence": 0.5,
                    }
                    for label, text in zip(pack["facts"]["cell_labels"], drafts, strict=True)
                ]
            }
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
