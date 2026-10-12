from pathlib import Path

import pytest

from dhf.generate import generate_document, partition_pack
from dhf.generate.validator import ID_PATTERN, validate_claims
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM


def test_validator_rules_and_numeric_units() -> None:
    pack = {"facts": {"passed": 39, "pressure_kpa": 80}, "evidence": [{"id": "SRS-021"}]}
    output = {
        "claims": [
            {"text": "Unknown source", "kind": "sourced", "citations": ["SRS-999"]},
            {"text": "SRS-999 is complete", "kind": "sourced", "citations": ["SRS-021"]},
            {"text": "40 passed", "kind": "sourced", "citations": ["SRS-021"]},
            {"text": "Uncited reasoning", "kind": "sourced", "citations": []},
            {"text": "39 passed at 80 kPa", "kind": "sourced", "citations": ["SRS-021"]},
        ]
    }
    result = validate_claims(output, pack, ["inferred", "suggested"])
    assert len(result["validation"]["rejected"]) == 3
    assert len(result["validation"]["downgraded"]) == 1
    assert len(result["validation"]["coerced"]) == 1
    assert [c["kind"] for c in result["claims"]] == ["inferred", "suggested"]
    assert result["claims"][0]["confidence"] == 0.5


def test_sstr_generation_citations_manifest_and_cache(tmp_path: Path) -> None:
    graph = ingest_fixtures()
    llm = LLM(root=tmp_path / "llm")
    generated = generate_document("sstr", graph, {"release": "1.1"}, out=tmp_path / "docs", llm=llm)
    manifest = generated["manifest"]
    assert len(manifest["sections"]) == 12
    assert all(not s["validation"]["rejected"] for s in manifest["sections"])
    ids = {a["id"] for a in graph["artifacts"]}
    assert {id.rstrip(".") for id in ID_PATTERN.findall(generated["markdown"])} <= ids
    assert all(id in ids for s in manifest["sections"] for id in s["cited_revisions"])
    assert all(
        c["kind"] == "suggested"
        for s in manifest["sections"]
        if s["id"] in ("release_conclusion", "residual_anomalies")
        for c in s["claims"]
    )
    summary = next(s for s in manifest["sections"] if s["id"] == "results_summary")
    assert summary["facts"]["summary"]["passed"] == 39
    import json

    golden = json.loads(Path("eval/golden/sstr_deterministic.json").read_text())
    assert {
        s["id"]: s["markdown"] for s in manifest["sections"] if s["mode"] == "deterministic"
    } == golden
    assert "**[Suggested — review required]**" in generated["markdown"]
    second = generate_document("sstr", graph, {"release": "1.1"}, out=tmp_path / "docs", llm=llm)
    assert second["manifest"]["telemetry"]["calls"] == 0
    assert second["markdown"] == generated["markdown"]
    assert manifest["generator_version"] and len(manifest["document_sha256"]) == 64
    assert len(manifest["source_snapshot"]) == 248


def test_prompt_bound_is_enforced_without_truncation() -> None:
    pack = {"facts": {}, "evidence": [{"id": str(i), "body": "x" * 20} for i in range(10)]}
    chunks = partition_pack(pack, 150)
    assert [a["id"] for chunk in chunks for a in chunk["evidence"]] == [str(i) for i in range(10)]
    with pytest.raises(ValueError, match="Single artifact"):
        partition_pack({"facts": {}, "evidence": [{"id": "SRS-001", "body": "x" * 200}]}, 100)
