import copy
import hashlib
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

from dhf.evaluation import clause_coverage, evaluate, impact_score
from dhf.generate import generate_document
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.render.diagram import diagram_bytes, diagram_layout
from dhf.review.audit import audit_pack, verify_audit


def test_local_png_is_repeatable_and_word_has_figure(tmp_path):
    result = generate_document(
        "sad", ingest_fixtures(), {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path / "llm")
    )
    source = (tmp_path / "sad.architecture.mmd").read_text()
    layout = diagram_layout(source)
    assert len(layout["components"]) == 6
    assert sum(len(c["units"]) for c in layout["components"]) == 20
    assert len(layout["external"]) == 2
    assert layout["dependencies"] == [
        {"from": "COMP_03", "to": "COMP_04", "call": "kestrel.alarm_latch.latched"}
    ]
    png = (tmp_path / "sad.architecture.png").read_bytes()
    assert png.startswith(b"\x89PNG") and png == diagram_bytes(source)
    doc = Document(tmp_path / "sad.docx")
    assert len(doc.inline_shapes) == 1
    assert any(p.text.lstrip("\u200b").startswith("Figure 1.") for p in doc.paragraphs)
    assert not any(p.text.startswith("flowchart") for p in doc.paragraphs)
    assert {d["format"] for d in result["manifest"]["diagrams"]} == {"mermaid-source", "local-png"}


def test_audit_checks_payload_hashes_and_missing_source_revisions(tmp_path):
    graph = ingest_fixtures()
    generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path / "docs", llm=LLM(root=tmp_path / "llm")
    )
    target = tmp_path / "audit.zip"
    result = audit_pack([graph], tmp_path / "docs", target, "1.1")
    assert result["verified_files"] >= 10
    with ZipFile(target) as archive:
        content = {n: archive.read(n) for n in archive.namelist()}
    assert {
        "documents/sstr.md",
        "evidence/snapshot-1.json",
        "trace/gaps.md",
        "clause_coverage.md",
        "SHA256SUMS",
    } <= content.keys()
    assert b"Recommended action" in content["trace/gaps.md"]
    assert b"UNIT-sensor_pressure" in content["trace/rtm.md"]
    incomplete = copy.deepcopy(graph)
    incomplete["artifacts"] = [a for a in incomplete["artifacts"] if a["id"] != "SRS-021"]
    incomplete["links"] = [
        link
        for link in incomplete["links"]
        if link["src"] != "SRS-021" and link["dst"] != "SRS-021"
    ]
    with pytest.raises(ValueError, match="Missing source revision: SRS-021"):
        audit_pack([incomplete], tmp_path / "docs", tmp_path / "missing.zip", "1.1")
    tampered = tmp_path / "tampered.zip"
    content["documents/sstr.md"] += b"Changed after checksum"
    with ZipFile(tampered, "w") as archive:
        for name, value in content.items():
            archive.writestr(name, value)
    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_audit(tampered)
    (tmp_path / "docs/sstr.md").write_text("Tampered local document")
    with pytest.raises(ValueError, match="Document checksum"):
        audit_pack([graph], tmp_path / "docs", tmp_path / "bad.zip", "1.1")


def test_extensibility_adds_only_yaml_and_filters_real_unit_results(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    shutil.copytree("specs", workspace / "specs")
    specs = {
        doc: (workspace / "specs/documents" / f"{doc}.yaml").read_text() for doc in ("sutr", "rtm")
    }
    for doc in specs:
        (workspace / "specs/documents" / f"{doc}.yaml").unlink()
    original = {
        str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in Path("src").rglob("*.py")
    }
    graph = ingest_fixtures()
    monkeypatch.chdir(workspace)
    llm = LLM(root=tmp_path / "llm")
    for doc, config in specs.items():
        (workspace / "specs/documents" / f"{doc}.yaml").write_text(config)
        result = generate_document(doc, graph, {"release": "1.1"}, out=workspace / "docs", llm=llm)
        assert result["manifest"]["doc_id"] == doc
    assert {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in original} == original
    summary = (
        result["manifest"]
        if result["manifest"]["doc_id"] == "sutr"
        else json.loads((workspace / "docs/sutr.manifest.json").read_text())
    )
    assert summary["sections"][0]["facts"]["summary"]["total"] == 0
    assert "No explicitly recorded unit-level results" in (workspace / "docs/sutr.md").read_text()
    changed = copy.deepcopy(graph)
    case = next(a for a in changed["artifacts"] if a["id"] == "TC-021")
    case["attributes"]["level"] = "unit"
    result = generate_document(
        "sutr", changed, {"release": "1.1"}, out=workspace / "unit-docs", llm=llm
    )
    assert result["manifest"]["sections"][0]["facts"]["summary"] == {
        "release": "1.1",
        "total": 1,
        "passed": 1,
        "failed": 0,
        "blocked": 0,
        "not_run": 0,
    }


def test_metrics_detect_invented_ids_and_do_not_score_missing_impact_as_perfect(tmp_path):
    graph = ingest_fixtures()
    result = generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path / "llm")
    )
    metrics = evaluate(graph, graph, [result["manifest"]], {"sstr": result["markdown"]})
    assert metrics["unknown_id_count"] == 0
    assert metrics["gap_detection"]["precision"] == metrics["gap_detection"]["recall"] == 1
    assert metrics["consistency"]["historical_score"]["true_positive"] == 2
    assert all(not r["mismatches"] for r in metrics["deterministic_goldens"].values())
    assert impact_score(None, {})["status"].startswith("pending")
    assert (
        impact_score([], {"sad": {"architecture": {"status": "stale", "artifacts": ["SRS-021"]}}})[
            "recall"
        ]
        == 0
    )
    mutated = evaluate(
        graph, graph, [result["manifest"]], {"sstr": result["markdown"] + "\nSRS-999 invented"}
    )
    assert mutated["unknown_ids"] == ["SRS-999"]
    appendix = clause_coverage([result["manifest"]])
    assert next(r for r in appendix["rows"] if r["clause"] == "IEC 62304 5.5")["status"].startswith(
        "UNCOVERED"
    )
