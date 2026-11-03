from typing import Any


class MockAdapter:
    """Deterministic fixture prose: not a substitute for a live quality check."""

    def complete(
        self, model: str, prompt: str, pack: dict[str, Any], limit: int, schema: dict | None = None
    ) -> dict:
        if pack.get("facts", {}).get("support_subject"):
            import re

            subject = pack["facts"]["support_subject"]
            text = subject["text"].lower()
            source = " ".join(a["body"] for a in pack["evidence"]).lower()
            words = set(re.findall(r"[a-z]+", text))
            overlap = len(words & set(re.findall(r"[a-z]+", source))) / max(1, len(words))
            support = (
                "supported" if text in source else "partial" if overlap >= 0.7 else "unsupported"
            )
            return {
                "results": [
                    {
                        "claim_key": subject["claim_key"],
                        "support": support,
                        "rationale": {
                            "text": "Mock lexical comparison; semantic support needs human review.",
                            "kind": "suggested",
                            "citations": [a["id"] for a in pack["evidence"]],
                            "confidence": 0.5,
                        },
                    }
                ]
            }
        evidence = pack.get("evidence", [])
        kind = pack.get("preferred_kind", "sourced")
        if pack.get("facts", {}).get("review_drafting"):
            from pathlib import Path

            import yaml

            template = yaml.safe_load(Path("specs/mock/review.yaml").read_text(encoding="utf-8"))[
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
            if rule in ("L01", "L03") and (rule == "L03" or pack["facts"]["subject"] != "SRS-020"):
                return {"claims": []}
            text = yaml.safe_load(Path("specs/mock/proposals.yaml").read_text(encoding="utf-8"))[
                rule
            ]
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
            if pack["facts"].get("unit_function"):
                from pathlib import Path

                import yaml

                drafts = yaml.safe_load(
                    Path("specs/mock/function_risk.yaml").read_text(encoding="utf-8")
                )
                unit = pack["facts"]["unit"]
                hazards = [a["id"] for a in evidence if a["id"].startswith("HAZ-")]
                return {
                    "claims": [
                        {
                            "text": label
                            + ": "
                            + drafts[label].format(function=pack["facts"]["unit_function"]),
                            "kind": "suggested",
                            "citations": [unit, *hazards],
                            "confidence": 0.5,
                        }
                        for label in pack["facts"]["cell_labels"]
                    ]
                }
            hazard = next(a for a in evidence if a["id"] == pack["facts"]["hazard"])
            body = hazard["body"]
            cause = body.split("Cause sequence: ", 1)[1].split(". ", 1)[0]
            harm = body.split("Foreseeable harm: ", 1)[1].split(". ", 1)[0]
            drafts = [
                hazard["title"],
                cause,
                "Unsafe output or retained state does not reflect the initiating condition",
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
        if "scope" in pack.get("facts", {}) and "verification_runs" in pack["facts"]:
            # Reference context is available for validation, not purpose prose.
            evidence = [a for a in evidence if a["id"].startswith("UN-")]
        from dhf.models.values import cut_at_word, opening_sentence

        def quoted(body: str) -> str:
            # Document sections run to thousands of characters; quote their opening.
            return body if len(body) <= 1000 else opening_sentence(body) or cut_at_word(body, 1000)

        return {
            "claims": [
                {
                    "text": (
                        f"{item['title']} is implemented in {item['properties']['Path']}."
                        if item["id"].startswith("UNIT-") and "Path" in item.get("properties", {})
                        else quoted(item["body"])
                    ),
                    "kind": kind,
                    "citations": [item["id"]],
                    "confidence": 1.0,
                }
                for item in [a for a in evidence if a.get("body")][:3]
            ]
        }
