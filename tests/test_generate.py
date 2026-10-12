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
    chunks = partition_pack(pack, 50)
    assert len(chunks) > 1
    assert [a["id"] for chunk in chunks for a in chunk["evidence"]] == [str(i) for i in range(10)]
    with pytest.raises(ValueError, match="Single artifact"):
        partition_pack({"facts": {}, "evidence": [{"id": "SRS-001", "body": "x" * 600}]}, 100)


def test_claim_limit_is_validated_and_audited() -> None:
    pack = {"facts": {}, "evidence": [{"id": "SRS-021"}]}
    output = {
        "claims": [
            {"text": text, "kind": "sourced", "citations": ["SRS-021"]}
            for text in ("First point", "Second point", "Third point")
        ]
    }
    result = validate_claims(output, pack, ["sourced"], max_claims=2)
    assert len(result["claims"]) == 2
    assert result["validation"]["rejected"] == [{"claim_index": 2, "reason": "max_claims"}]


@pytest.mark.parametrize("reason", ["refusal", "max_tokens", "unparseable", "provider_error"])
def test_unavailable_section_becomes_manual_placeholder_without_retries(
    tmp_path: Path, reason: str
) -> None:
    from dhf.llm.adapters.mock import MockAdapter
    from dhf.llm.errors import DraftingUnavailable
    from dhf.review import readiness

    class RefusingAdapter:
        refused_calls = 0

        def complete(self, model, prompt, pack, limit):
            if "open_count" in pack["facts"]:
                self.refused_calls += 1
                raise DraftingUnavailable(reason, "anthropic", category="safety_classifier")
            return MockAdapter().complete(model, prompt, pack, limit)

    adapter = RefusingAdapter()
    result = generate_document(
        "sstr",
        ingest_fixtures(),
        {"release": "1.1"},
        out=tmp_path / "docs",
        llm=LLM(root=tmp_path / "llm", adapter=adapter),
    )
    failed = next(s for s in result["manifest"]["sections"] if s["id"] == "residual_anomalies")
    assert failed["status"] == "ai_unavailable" and failed["claims"] == []
    assert failed["ai_unavailable"]["reason"] == reason
    assert failed["ai_unavailable"]["stop_details"]["category"] == "safety_classifier"
    assert f"AI drafting unavailable ({reason}) — author manually." in result["markdown"]
    assert adapter.refused_calls == 1
    assert len(result["manifest"]["sections"]) == 12
    assert (tmp_path / "docs/sstr.manifest.json").is_file()
    assert (
        next(s for s in result["manifest"]["sections"] if s["id"] == "results_summary")["facts"][
            "summary"
        ]["passed"]
        == 39
    )
    assert {"section": "residual_anomalies", "reason": "ai_unavailable"} in readiness(
        result["markdown"], result["manifest"]
    )["blockers"]


def test_real_id_shapes_and_single_call_synthesis(tmp_path: Path) -> None:
    from dhf.generate import generate_section, load_spec
    from dhf.graph.queries import prompt_pack, query

    pack = {"facts": {"coverage": 88.57}, "evidence": [{"id": "RUN-2"}, {"id": "SRS-021"}]}
    claims = {
        "claims": [
            {
                "text": "SRS-to-test and SRS-to-code coverage is 88.57 for RUN-2.",
                "kind": "sourced",
                "citations": ["RUN-2"],
            },
            {"text": "SRS-999 is verified.", "kind": "sourced", "citations": ["RUN-2"]},
        ]
    }
    checked = validate_claims(claims, pack, ["sourced"])
    assert len(checked["claims"]) == 1 and len(checked["validation"]["rejected"]) == 1
    graph = ingest_fixtures()
    llm = LLM(root=tmp_path)
    for id in ("purpose_scope", "release_conclusion"):
        section = next(s for s in load_spec("sstr")["sections"] if s["id"] == id)
        before = llm.calls
        result = generate_section(section, graph, {"release": "1.1"}, llm)
        assert result["status"] == "draft" and llm.calls - before == 1
    view = prompt_pack(query(graph, "residual_anomalies", {"release": "1.1"}))
    assert view["evidence"][0]["properties"]["Listed as residual anomaly"] == "yes"
    assert "residual_listed" not in str(view)


def test_exact_url_citations_are_normalized_but_lookalikes_rejected() -> None:
    pack = {
        "facts": {},
        "evidence": [{"id": "RES-2-008", "source": {"url": "fixture://RES-2-008"}}],
    }
    output = {
        "claims": [
            {"text": "The retest failed.", "kind": "sourced", "citations": [url]}
            for url in ("fixture://RES-2-008", "fixture://RES-2-008?rev=1", "fixture://RES-2-999")
        ]
    }
    result = validate_claims(output, pack, ["sourced"])
    assert result["claims"][0]["citations"] == ["RES-2-008"]
    assert len(result["claims"]) == 1
    assert len(result["validation"]["rejected"]) == 2
    assert result["validation"]["normalized"] == [
        {
            "claim_index": 0,
            "reason": "exact_source_url",
            "from": "fixture://RES-2-008",
            "to": "RES-2-008",
        }
    ]


@pytest.mark.parametrize("kind", ["evidence_over_budget", "invalid_output", "budget_exceeded"])
def test_local_drafting_failures_have_distinct_safe_reasons(
    tmp_path: Path, monkeypatch, kind: str
) -> None:
    import dhf.generate as generation
    from dhf.llm import BudgetExceeded

    section = generation.load_spec("sstr")["sections"][0]
    llm = LLM(root=tmp_path)
    if kind == "evidence_over_budget":
        original = generation.load_prompt
        monkeypatch.setattr(
            generation,
            "load_prompt",
            lambda reference: {
                **original(reference),
                "max_input_tokens": 1,
            },
        )
    else:

        def fail(*args, **kwargs):
            if kind == "budget_exceeded":
                raise BudgetExceeded("LLM budget cap reached")
            return {"claims": "malformed"}

        monkeypatch.setattr(llm, "generate", fail)
    result = generation.generate_section(section, ingest_fixtures(), {"release": "1.1"}, llm)
    assert result["status"] == "ai_unavailable"
    assert result["ai_unavailable"]["reason"] == kind
    assert result["ai_unavailable"]["internal_message"]
