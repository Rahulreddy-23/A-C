import copy
import json
from pathlib import Path

import pytest

from dhf.generate import generate_document
from dhf.generate.validator import validate_claims
from dhf.graph.reviews import risk_gaps, risk_rows
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.propose import propose


def test_risk_source_only_severity_suggestions_and_gaps(tmp_path):
    graph = ingest_fixtures()
    result = generate_document(
        "sfmea", graph, {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path / "llm")
    )
    rows = [
        row
        for s in result["manifest"]["sections"]
        if s["query"] == "sfmea_rows"
        for row in s["facts"]["rows"]
    ]
    source = {
        a["id"]: a["attributes"]["severity"] for a in graph["artifacts"] if a["type"] == "hazard"
    }
    assert {r["hazard"]: r["severity"] for r in rows} == source
    claims = [c for s in result["manifest"]["sections"] for c in s["claims"]]
    assert len(claims) == 40 and all(c["kind"] == "suggested" for c in claims)
    assert not any(s["status"] == "ai_unavailable" for s in result["manifest"]["sections"])
    assert "**[Suggested — review required]**" in result["markdown"]
    assert "Residual-risk assessment and acceptance" in result["markdown"]
    assert {
        "rule": "F02",
        "artifact": "RC-12",
        "action": "Record a requirement and verifying test for this control.",
    } in result["manifest"]["risk_gaps"]
    assert len([f for f in result["manifest"]["risk_gaps"] if f["rule"] == "F03"]) == 8
    broken = copy.deepcopy(graph)
    broken["links"] = [
        e for e in broken["links"] if not (e["type"] == "mitigates" and e["dst"] == "HAZ-04")
    ]
    assert any(f["rule"] == "F01" and f["artifact"] == "HAZ-04" for f in risk_gaps(broken))
    assert len(risk_rows(graph)) == 8
    pack = {
        "facts": {"risk_authoring": True, "cell_labels": ["Failure mode"], "severity": 5},
        "evidence": [{"id": "HAZ-01"}],
    }
    output = {
        "claims": [
            {
                "text": "Failure mode: Severity 5 assigned.",
                "kind": "suggested",
                "citations": ["HAZ-01"],
                "confidence": 0.9,
            }
        ]
    }
    assert (
        validate_claims(output, pack, ["suggested"])["validation"]["rejected"][0]["reason"]
        == "risk_authoring_contract"
    )


def test_drr_inputs_not_invented_and_proposals_are_separate(tmp_path):
    graph = ingest_fixtures()
    llm = LLM(root=tmp_path / "llm")
    with pytest.raises(ValueError, match="review_input"):
        generate_document("drr", graph, {"release": "1.1"}, out=tmp_path, llm=llm)
    review = json.loads(Path("data/synthetic/review_input.json").read_text())
    result = generate_document(
        "drr",
        graph,
        {"release": "1.1", "review_input": review, "previous_snapshot": graph},
        out=tmp_path,
        llm=llm,
    )
    assert not any(s["status"] == "ai_unavailable" for s in result["manifest"]["sections"])
    identification = result["manifest"]["sections"][0]
    assert {r["field"]: r["value"] for r in identification["facts"]["rows"]} == review
    assert result["manifest"]["sections"][1]["facts"]["rows"] == []
    assert {s["id"] for s in result["manifest"]["sections"] if s["mode"] == "human"} == {
        "discussion",
        "decisions",
        "new_actions",
        "approvals",
    }
    assert all(
        c["kind"] == "suggested" for s in result["manifest"]["sections"] for c in s["claims"]
    )
    checklist = next(s for s in result["manifest"]["sections"] if s["id"] == "checklist")
    assert all(c["text"].endswith("?") for c in checklist["claims"])
    before = copy.deepcopy(graph)
    proposals = propose(graph, [], tmp_path / "proposals", llm)
    assert graph == before
    assert len(proposals["sections"]) == 42
    assert {s["id"].split(".")[0] for s in proposals["sections"]} == {"L01", "L02", "L03"}
    orphan = next(s for s in proposals["sections"] if s["id"].startswith("L02"))
    assert "The software shall produce a bounded diagnostic trace" in orphan["claims"][0]["text"]
    assert all(
        c["kind"] == "suggested" and c["confidence"] is not None
        for s in proposals["sections"]
        for c in s["claims"]
    )


def test_safety_cases_have_concrete_stimuli():
    graph = ingest_fixtures()
    nodes = {a["id"]: a for a in graph["artifacts"]}
    for id, stimulus in [
        ("TC-001", "120.01"),
        ("TC-002", "60 s"),
        ("TC-008", "0.11"),
        ("TC-013", "unsafe=True"),
        ("TC-018", "10.01"),
        ("TC-021", "t=2.99"),
    ]:
        assert stimulus in nodes[id]["body"]
        assert "case 0" not in nodes[id]["title"]


def test_risk_trace_follows_hazard_function_instead_of_index():
    graph = ingest_fixtures()
    rows = {r["hazard"]: r for r in risk_rows(graph)}
    assert set(rows["HAZ-04"]["requirements"]) == {
        "SRS-009",
        "SRS-012",
        "SRS-021",
        "SRS-022",
        "SRS-023",
    }
    assert {"UNIT-sensor_pressure", "UNIT-sensor_filter", "UNIT-alarm_latch"} <= set(
        rows["HAZ-04"]["units"]
    )
    assert "TC-021" in rows["HAZ-04"]["verification"]
    assert rows["HAZ-06"]["requirements"] == ["SRS-018", "SRS-019", "SRS-020"]
    assert rows["HAZ-07"]["requirements"] == ["SRS-024", "SRS-025", "SRS-033"]
    assert rows["HAZ-08"]["requirements"] == ["SRS-029", "SRS-030"]
    from dhf.trace import gaps

    assert [f["artifact_id"] for f in gaps(graph) if f["rule"] == "G06"] == ["RC-12"]
    assert [f["artifact_id"] for f in gaps(graph) if f["rule"] == "G07"] == ["SRS-012"]
