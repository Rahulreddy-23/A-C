import copy
from zipfile import ZipFile

from dhf.evaluation import evaluate, metrics_markdown
from dhf.generate import generate_document, load_prompt
from dhf.generate.support import support_comments, verify_document
from dhf.generate.validator import validate_claims
from dhf.graph.queries import prompt_pack, query
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.models import SupportChecks, strict_output_schema
from dhf.models.values import numbers
from dhf.render import render_docx
from dhf.review import readiness


def test_unsupported_is_flagged_commented_and_not_removed_or_a_gate(tmp_path):
    graph = ingest_fixtures()
    result = generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path / "llm")
    )
    original = copy.deepcopy(result["manifest"])
    claim = next(c for s in original["sections"] for c in s["claims"] if c["kind"] == "sourced")
    old = claim["text"]
    claim["text"] = "The controller cures every illness without any adverse consequence."
    markdown = result["markdown"].replace(old, claim["text"])
    verified = verify_document(graph, original, LLM(root=tmp_path / "verify"), sample=0)
    assert any(r["support"] == "unsupported" for r in verified["claim_support"]["results"])
    assert [s["claims"] for s in verified["sections"]] == [
        s["claims"] for s in original["sections"]
    ]
    assert readiness(markdown, original) == readiness(markdown, verified)
    word = tmp_path / "supported.docx"
    render_docx(markdown, word, support_findings=support_comments(verified))
    with ZipFile(word) as archive:
        assert b"Advisory support assessment: unsupported" in archive.read("word/comments.xml")
        assert claim["text"].encode() in archive.read("word/document.xml")
    metrics = evaluate(graph, graph, [verified], {"sstr": markdown})
    text = metrics_markdown(metrics)
    assert "Assumed authoring hours" in text and "not measured labor savings" in text
    assert metrics["documents"][0]["claim_support"]["counts"]["unsupported"] >= 1


def test_collaborators_have_compact_provider_context_and_unit_numbers():
    graph = ingest_fixtures()
    pack = query(graph, "component_design", {"entity": "COMP-03"})
    assert {"COMP-01", "COMP-02", "COMP-04", "COMP-05"} <= {a["id"] for a in pack["evidence"]}
    compact = prompt_pack(pack)
    assert next(a for a in compact["evidence"] if a["id"] == "COMP-02")["body"] == ""
    assert next(a for a in compact["evidence"] if a["id"] == "COMP-03")["body"]
    assert numbers("Hold for 3s, allocate 256bytes; use sha256, SRS-021") == {"3", "256"}
    assert numbers("Dwell 1.5s; count 39. sha256.") == {"1.5", "39"}
    source = {"facts": {"source_numbers": ["3", "256"]}, "evidence": [{"id": "SRS-021"}]}
    output = {
        "claims": [
            {
                "text": "Hold 3s and allocate 256bytes.",
                "kind": "sourced",
                "citations": ["SRS-021"],
                "confidence": 1,
            }
        ]
    }
    assert len(validate_claims(output, source, ["sourced"])["claims"]) == 1
    source["facts"]["source_numbers"] = ["3", "64"]
    assert not validate_claims(output, source, ["sourced"])["claims"]
    assert "do not return sourced or inferred kinds" in load_prompt("sstr.conclusion@3")["body"]


def test_support_schema_and_default_cache_budget_contract(tmp_path):
    llm = LLM(root=tmp_path)
    pack = {
        "facts": {"support_subject": {"claim_key": "key", "text": "Deliver configured flow."}},
        "evidence": [
            {"id": "SRS-001", "body": "Deliver configured flow.", "attributes": {"synthetic": True}}
        ],
    }
    result = llm.generate("verify.support", 1, "p", pack, output_schema="support.v1")
    assert SupportChecks.model_validate(result).results[0].support == "supported"
    llm.generate("verify.support", 1, "p", pack, output_schema="support.v1")
    assert llm.calls == 1 and llm.hits == 1
    assert strict_output_schema("support.v1")["additionalProperties"] is False
