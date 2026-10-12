"""Pure claim-validation step: typed JSON in, typed/cited claims and audit events out."""

import re
from decimal import Decimal

from dhf.models import Claims

ID_PATTERN = re.compile(
    r"\b(?:UN|SYS|SRS|HAZ|RC|COMP|TC|BUG|PR|RUN|RES|UNIT|SOUP|ADR|ACT|REV)-[A-Za-z0-9_.-]+"
)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:\.\d+)?(?![A-Za-z0-9_])")


def numbers(text: str) -> set[str]:
    text = ID_PATTERN.sub("", text)
    return {format(Decimal(n).normalize(), "f") for n in NUMBER_PATTERN.findall(text)}


def fact_numbers(value: object) -> set[str]:
    if isinstance(value, dict):
        return set().union(*(fact_numbers(v) for v in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(fact_numbers(v) for v in value)) if value else set()
    if isinstance(value, bool) or value is None:
        return set()
    return numbers(str(value))


def validate_claims(output: dict, pack: dict, allowed_kinds: list[str]) -> dict:
    claims = Claims.model_validate(output).model_dump(mode="json")["claims"]
    ids = {a["id"] for a in pack["evidence"]}
    permitted_numbers = fact_numbers(pack["facts"])
    accepted = []
    events = {"rejected": [], "downgraded": [], "coerced": []}
    for index, claim in enumerate(claims):
        unknown = (set(claim["citations"]) | set(ID_PATTERN.findall(claim["text"]))) - ids
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
        accepted.append(claim)
    return {
        "claims": Claims.model_validate({"claims": accepted}).model_dump(mode="json")["claims"],
        "validation": events,
    }
