import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dhf.generate.validator import validate_claims

ROOT = Path("tests/fixtures")


def test_validator_cases_cover_citations_confidence_and_numbers():
    sample = ROOT / "sad_component"
    pack = {
        "facts": json.loads((sample / "facts_json.txt").read_text()),
        "evidence": json.loads((sample / "evidence_json.txt").read_text()),
    }

    def check(claim: dict) -> dict:
        return validate_claims({"claims": [claim]}, pack, ["sourced", "inferred", "suggested"])

    base = {
        "text": "UNIT-sensor_pressure uses an 80 kPa threshold.",
        "kind": "sourced",
        "citations": ["UNIT-sensor_pressure"],
        "confidence": 1.0,
    }
    assert len(check(base)["claims"]) == 1
    assert (
        check({**base, "citations": ["SRS-999"]})["validation"]["rejected"][0]["reason"]
        == "unknown_ids"
    )
    assert (
        check({**base, "text": "SRS-999 uses 80 kPa."})["validation"]["rejected"][0]["reason"]
        == "unknown_ids"
    )
    assert (
        check({**base, "text": "The limit is 81 kPa."})["validation"]["rejected"][0]["reason"]
        == "numbers_match_facts"
    )
    assert (
        check({**base, "citations": []})["validation"]["downgraded"][0]["reason"]
        == "sourced_without_citation"
    )
    for value in (None, -0.1, 1.1):
        with pytest.raises(ValidationError):
            check({**base, "kind": "inferred", "confidence": value})
    numeric_pack = {**pack, "facts": {"observed": 39.0}}
    accepted = validate_claims(
        {"claims": [{**base, "text": "39 passed."}]}, numeric_pack, ["sourced"]
    )
    assert len(accepted["claims"]) == 1
    rejected = validate_claims(
        {"claims": [{**base, "text": "40 passed."}]}, numeric_pack, ["sourced"]
    )
    assert rejected["validation"]["rejected"][0]["reason"] == "numbers_match_facts"
