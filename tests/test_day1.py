import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dhf.generate.validator import validate_claims

ROOT = Path("port/copilot_studio/day1")


@pytest.mark.parametrize(
    ("name", "source"),
    [("sstr_anomaly", "sstr.anomaly_assessment"), ("sad_component", "design.component")],
)
def test_ready_prompt_samples_reproduce_reference_validation(name: str, source: str):
    sample = ROOT / "samples" / name
    facts = json.loads((sample / "facts_json.txt").read_text())
    evidence = json.loads((sample / "evidence_json.txt").read_text())
    output = json.loads((sample / "expected_claims.json").read_text())
    result = validate_claims(
        output, {"facts": facts, "evidence": evidence}, ["sourced", "inferred", "suggested"], 2
    )
    assert result["claims"] == output["claims"]
    assert not any(result["validation"].values())
    assert all(a["source"]["revision"] and a["content_hash"] for a in evidence)
    prompt_body = Path(f"specs/prompts/{source}.md").read_text().split("---\n", 2)[2].strip()
    ready = (ROOT / f"{name}_prompt.md").read_text()
    assert prompt_body in ready
    assert all(
        f"[[{key}]]" in ready
        for key in ("facts_json", "evidence_json", "max_claims", "preferred_kind")
    )


def test_day1_validator_cases_cover_citations_confidence_and_numbers():
    sample = ROOT / "samples" / "sad_component"
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
    snippets = (ROOT / "validator_powerfx.md").read_text()
    for token in (
        "LookUp(EvidenceIds",
        "ClaimKind",
        "ClaimConfidence",
        "MatchAll(",
        "FullMatch",
        "numeric_unverified",
    ):
        assert token in snippets


def test_dataverse_column_worksheet_covers_four_mvp_tables():
    rows = list(csv.DictReader((ROOT / "mvp_columns.csv").open()))
    assert {r["table"] for r in rows} == {
        "Artifact",
        "TraceLink",
        "DocumentSection",
        "GenerationRun",
    }
    assert len(rows) >= 40
    assert all(r["logical_name"].startswith("dhf_") and r["type"] for r in rows)
    assert all(
        any(r["alternate_key"] == "yes" for r in rows if r["table"] == table)
        for table in {r["table"] for r in rows}
    )
    click_path = (ROOT / "click_path_tier_b.md").read_text()
    assert all(f"Flow {i:02}" in click_path for i in range(1, 8))
    assert "never" in click_path.lower() or "do not" in click_path.lower()
