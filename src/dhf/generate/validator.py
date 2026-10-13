"""Pure claim-validation step: typed JSON in, typed/cited claims and audit events out."""

from dhf.models import Claims
from dhf.models.values import ID_PATTERN, fact_numbers, numbers


def validate_claims(
    output: dict, pack: dict, allowed_kinds: list[str], max_claims: int | None = None
) -> dict:
    claims = Claims.model_validate(output).model_dump(mode="json")["claims"]
    ids = {a["id"] for a in pack["evidence"]}
    permitted_numbers = fact_numbers(pack["facts"])
    accepted = []
    events = {"rejected": [], "downgraded": [], "coerced": [], "normalized": []}
    urls = {}
    for artifact in pack["evidence"]:
        url = artifact.get("source", {}).get("url")
        if url:
            urls.setdefault(url, set()).add(artifact["id"])
    for index, claim in enumerate(claims):
        if pack["facts"].get("risk_authoring"):
            import re

            label = claim["text"].split(":", 1)[0]
            if label not in pack["facts"]["cell_labels"] or re.search(
                r"\b(severity|probability|RPN|residual risk)\b", claim["text"], re.I
            ):
                events["rejected"].append(
                    {"claim_index": index, "reason": "risk_authoring_contract"}
                )
                continue
        for position, citation in enumerate(claim["citations"]):
            matches = urls.get(citation, set())
            if len(matches) == 1:
                id = next(iter(matches))
                claim["citations"][position] = id
                events["normalized"].append(
                    {"claim_index": index, "reason": "exact_source_url", "from": citation, "to": id}
                )
        unknown = (
            set(claim["citations"]) | {id.rstrip(".") for id in ID_PATTERN.findall(claim["text"])}
        ) - ids
        if unknown:
            events["rejected"].append(
                {"claim_index": index, "reason": "unknown_ids", "ids": sorted(unknown)}
            )
            continue
        mismatched = numbers(claim["text"]) - permitted_numbers
        if mismatched:
            events["rejected"].append(
                {
                    "claim_index": index,
                    "reason": "numbers_match_facts",
                    "numbers": sorted(mismatched),
                }
            )
            continue
        if claim["kind"] == "sourced" and not claim["citations"]:
            claim["kind"] = "inferred"
            claim["confidence"] = claim["confidence"] if claim["confidence"] is not None else 0.5
            events["downgraded"].append(
                {"claim_index": index, "reason": "sourced_without_citation"}
            )
        if claim["kind"] not in allowed_kinds:
            claim["kind"] = "suggested"
            claim["confidence"] = claim["confidence"] if claim["confidence"] is not None else 0.5
            events["coerced"].append({"claim_index": index, "reason": "allowed_kinds"})
        if max_claims is not None and len(accepted) >= max_claims:
            events["rejected"].append({"claim_index": index, "reason": "max_claims"})
            continue
        accepted.append(claim)
    return {
        "claims": Claims.model_validate({"claims": accepted}).model_dump(mode="json")["claims"],
        "validation": events,
    }
