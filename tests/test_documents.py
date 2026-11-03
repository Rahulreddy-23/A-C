"""Document-baseline import over synthetic Word/CSV files shaped like a legacy DHF."""

import json
from pathlib import Path

import yaml
from docx import Document
from typer.testing import CliRunner

from dhf.cli import app
from dhf.ingest.documents import import_folder
from dhf.trace import evaluate_rules, unassessable_rules
from dhf.trace.reports import gap_rules, gaps_markdown

PROFILE = Path("specs/doc_import/dhf_documents.yaml")


def table(document, rows: list[list[str]]) -> None:
    grid = document.add_table(rows=len(rows), cols=len(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            grid.cell(r, c).text = value


def prd(path: Path, ids: list[str]) -> None:
    document = Document()
    document.add_heading("Product Requirements Document", 0)
    document.add_heading("Functional Requirements", 1)
    header = ["Req ID", "Short Text", "Requirement Text", "Release", "Req Type"]
    table(
        document, [header] + [[i, f"Need {i}", f"{i} shall hold.", "R1", "Functional"] for i in ids]
    )
    document.save(path)


def unit(document, name: str, sections: list[str]) -> None:
    document.add_heading(name, 3)
    document.add_heading("Software Unit Description", 4)
    document.add_paragraph(f"{name} purpose.")
    for section in sections:
        document.add_heading(section, 4)
        document.add_paragraph(f"{name} {section.lower()}.")


def build(folder: Path) -> None:
    prd(folder / "Kestrel PRD #2.docx", ["PREQ-KS-1", "PREQ-KS-2", "PREQ-KS-3", "PREQ-KS-4"])
    prd(folder / "Kestrel PRD #1.docx", ["PREQ-KS-1"])
    prd(folder / "Kestrel PRD #3 redlines.docx", ["PREQ-KS-9"])

    srs = Document()
    srs.add_heading("System Features", 1)
    srs.add_heading("Fleet", 2)
    table(srs, [["Spec ID", "SW Feature", "Spec Type"], ["SPEC-KS-10", "Fleet view", "Functional"]])
    srs.add_paragraph("Title: Fleet - Pump list")
    srs.add_paragraph("Description:")
    srs.add_paragraph("The application lists every pump.")
    table(srs, [["Label", "Value"], ["Serial", "Pump serial"]])
    table(srs, [["Spec ID", "SW Feature", "Spec Type"], ["SPEC-KS-11", "Fleet view", "Security"]])
    srs.add_paragraph("Title: Fleet - Access")
    srs.add_paragraph("Description: Only authorized users see the fleet.")
    srs.save(folder / "Kestrel Software Specification v03.docx")

    sad = Document()
    sad.add_heading("Software Item Design", 1)
    sad.add_heading("Fleet Service", 2)
    sad.add_paragraph("Keeps the pump fleet.")
    sad.add_heading("Audit Store", 2)
    sad.add_paragraph("Stores audit events.")
    sad.add_heading("Requirements Matrix", 1)
    table(
        sad,
        [
            ["Req. ID", "Software Items"],
            ["PREQ-KS-1", "Fleet Service, Audit Store"],
            ["PREQ-KS-2", "N/A."],
            ["PREQ-KS-3", "Billing Engine"],
        ],
    )
    sad.save(folder / "Kestrel Software Architecture Document_v02.docx")

    sdd = Document()
    sdd.add_heading("Detailed Design", 1)
    sdd.add_heading("Fleet", 2)
    unit(sdd, "Ks.Fleet.Api", ["Processing Logic", "Error Handling"])
    unit(sdd, "Ks.Fleet.Core", ["Processing Logic"])
    sdd.add_heading("Shared Libraries", 2)
    unit(sdd, "Ks.Logging", [])
    sdd.save(folder / "Kestrel SDD - Fleet Service_v01.docx")

    (folder / "Test_Cases.csv").write_text(
        "﻿ID,Work Item Type,Title,Assigned To,State,Tags\n"
        '"5001","Test Case","Fleet list shows pumps","Pat Example <pat@example.com>","Approved",'
        '"Fleet; Regression"\n'
        '"5002","Test Case","Fleet access denied","Pat Example <pat@example.com>","Design",\n'
    )
    Document().save(folder / "REF Kestrel notes.docx")


def test_document_baseline_import_extracts_trace_and_flags_inconsistencies(tmp_path) -> None:
    build(tmp_path)
    graph, summary = import_folder(tmp_path, PROFILE)
    nodes = {a["id"]: a for a in graph["artifacts"]}
    assert summary["artifact_counts"] == {
        "component": 2,
        "software_req": 2,
        "software_unit": 3,
        "system_req": 4,
        "test_case": 2,
    }
    assert summary["notes"]["product requirements: older issues skipped"] == 1
    assert "Kestrel PRD #3 redlines.docx" in summary["excluded_files"]
    spec = nodes["SPEC-KS-10"]
    assert spec["title"] == "Fleet - Pump list" and spec["attributes"]["feature"] == "Fleet view"
    assert spec["body"] == "The application lists every pump.\nLabel | Value\nSerial | Pump serial"
    assert nodes["SPEC-KS-11"]["body"] == "Only authorized users see the fleet."
    assert spec["source"]["system"] == "file" and len(spec["source"]["revision"]) == 12
    assert nodes["PREQ-KS-2"]["attributes"]["allocation"] == "N/A"
    assert nodes["PREQ-KS-3"]["attributes"]["unresolved_allocations"] == ["Billing Engine"]
    core = nodes["UNIT-Fleet.Ks.Fleet.Core"]
    assert core["attributes"]["component"] == "SI-Fleet-Service"
    assert core["attributes"]["missing_sections"] == ["Error Handling"]
    edges = {(e["src"], e["dst"]) for e in graph["links"] if e["type"] == "allocated_to"}
    assert {("PREQ-KS-1", "SI-Fleet-Service"), ("PREQ-KS-1", "SI-Audit-Store")} <= edges
    assert nodes["TC-5001"]["attributes"]["tags"] == ["Fleet", "Regression"]
    assert "example.com" not in json.dumps(graph) and "Pat Example" not in json.dumps(graph)

    rules = yaml.safe_load(Path("specs/rules/document_baseline.yaml").read_text())["rules"]
    flagged = {}
    for finding in evaluate_rules(graph, rules):
        flagged.setdefault(finding["rule"], []).append(finding["artifact_id"])
    assert flagged == {
        "D01": ["PREQ-KS-3", "PREQ-KS-4"],
        "D02": ["PREQ-KS-3"],
        "D03": ["SI-Audit-Store"],
        "D04": ["UNIT-Shared-Libraries.Ks.Logging"],
        "D05": ["UNIT-Fleet.Ks.Fleet.Core", "UNIT-Shared-Libraries.Ks.Logging"],
    }


def test_rules_without_any_link_evidence_are_reported_as_not_assessable(tmp_path) -> None:
    build(tmp_path)
    graph, _ = import_folder(tmp_path, PROFILE)
    blind = unassessable_rules(graph, gap_rules())
    assert {"G01", "G04", "G08", "G09"} <= set(blind)
    report = gaps_markdown([], gap_rules(), blind)
    assert "| G01 | not assessable |" in report and "Ingest the system" in report


def test_import_docs_command_writes_store_and_report(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    build(tmp_path / "docs")
    result = CliRunner().invoke(
        app,
        [
            "import-docs",
            str(tmp_path / "docs"),
            "--db",
            str(tmp_path / "out" / "evidence.sqlite"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "software_req=2" in result.output and "baseline findings" in result.output
    report = (tmp_path / "out" / "import-report.md").read_text()
    assert "| D05 | 2 |" in report and "UNIT-Fleet.Ks.Fleet.Core" in report


def test_explorer_is_product_neutral_and_honest_about_document_baselines(tmp_path, monkeypatch):
    import base64
    import re

    from dhf.ingest.fixtures import ingest_fixtures
    from dhf.render.explorer import create_explorer

    def payload(html: str) -> dict:
        return json.loads(base64.b64decode(re.search(r"atob\('([A-Za-z0-9+/=]+)'\)", html)[1]))

    build(tmp_path)
    graph, _ = import_folder(tmp_path, PROFILE)
    monkeypatch.setenv("DHF_PRODUCT_NAME", "Fleetwatch")
    monkeypatch.setenv("DHF_RELEASE", "2.0")
    data = payload(create_explorer(graph, []))
    assert data["product"]["name"] == "Fleetwatch" and data["release"] == "2.0"
    assert data["product"]["evidence"] == "Confidential evidence, local only"
    assert {"G01", "G02", "G04"} <= set(data["not_assessable"])
    assert {f["rule"] for f in data["findings"]} == {"D01", "D02", "D03", "D04", "D05"}
    demo = payload(create_explorer(ingest_fixtures(), []))
    assert demo["not_assessable"] == [] and demo["product"]["evidence"] == "Synthetic evidence"
    assert not [f for f in demo["findings"] if f["rule"].startswith("D")]


def test_import_handles_word_features_and_matrix_edge_cases(tmp_path) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def tracked_insert(paragraph, text: str) -> None:
        ins = OxmlElement("w:ins")
        for key, value in (
            ("w:id", "9"),
            ("w:author", "reviewer"),
            ("w:date", "2026-01-01T00:00:00Z"),
        ):
            ins.set(qn(key), value)
        run, t = OxmlElement("w:r"), OxmlElement("w:t")
        t.text = text
        run.append(t)
        ins.append(run)
        paragraph._p.append(ins)

    header = ["Req ID", "Short Text", "Requirement Text", "Release", "Req Type"]
    document = Document()
    document.add_heading("Functional Requirements", 1)
    table(document, [header] + [[f"PREQ-KS-{n}", "Need", "Shall.", "R1", "F"] for n in range(1, 6)])
    grid = document.tables[0]
    row = grid.add_row()
    tracked_insert(row.cells[0].paragraphs[0], "PREQ-KS-7")  # added with Track Changes on
    row.cells[1].text = "Inserted need"
    table(document, [header, ["PREQ-KS-8", "Controlled", "Shall.", "R1", "F"]])
    controlled = document.tables[1]._tbl
    sdt, content = OxmlElement("w:sdt"), OxmlElement("w:sdtContent")
    controlled.addprevious(sdt)
    sdt.append(content)
    content.append(controlled)  # requirements table inside a content control
    document.save(tmp_path / "Kestrel PRD v1.10.docx")
    prd(tmp_path / "Kestrel PRD v1.9.docx", ["PREQ-KS-90"])
    prd(tmp_path / "Kestrel PRD v1.11 Redlines.DOCX", ["PREQ-KS-91"])
    (tmp_path / "~$strel PRD v1.10.docx").write_bytes(b"owner file")

    sad = Document()
    sad.add_heading("Software Item Design", 1)
    for item in ("UI", "Fleet Service", "Audit Store"):
        sad.add_heading(item, 2)
    sad.add_heading("Requirements Matrix", 1)
    table(
        sad,
        [
            ["Req. ID", "Software Items"],
            ["PREQ-KS-1", "Fleet Service"],
            ["PREQ-KS-2", ""],
            ["PREQ-KS-3", "-"],
            ["PREQ-KS-4", "Guidance Engine"],
            ["PREQ-KS-5", "?"],
        ],
    )
    sad.tables[0].rows[1].cells[1].add_paragraph("Audit Store")  # one item per line
    sad.save(tmp_path / "Kestrel Software Architecture Document_v02.docx")

    sdd = Document()
    sdd.add_heading("Detailed Design", 1)
    sdd.add_heading("Fleet", 2)
    sdd.add_heading("Ks.Fleet.Api", 3)
    sdd.add_paragraph("Preamble before the first design section.")
    sdd.add_heading("Software Unit Description", 4)
    sdd.add_paragraph("HTTP API.")
    sdd.save(tmp_path / "Kestrel SDD - Fleet Service_v01.docx")

    graph, summary = import_folder(tmp_path, PROFILE)
    nodes = {a["id"]: a for a in graph["artifacts"]}
    assert "Kestrel PRD v1.10.docx" in summary["imported_files"]
    assert {"Kestrel PRD v1.11 Redlines.DOCX", "~$strel PRD v1.10.docx"} <= set(
        summary["excluded_files"]
    )
    assert {"PREQ-KS-7", "PREQ-KS-8"} <= nodes.keys() and "PREQ-KS-90" not in nodes
    assert summary["notes"]["documents with tracked changes (read as accepted)"] == 1
    assert summary["notes"]["content controls read"] == 1
    edges = {(e["src"], e["dst"]) for e in graph["links"]}
    assert {("PREQ-KS-1", "SI-Fleet-Service"), ("PREQ-KS-1", "SI-Audit-Store")} <= edges
    assert not [e for e in edges if e[1] == "SI-UI"]
    assert "allocation" not in nodes["PREQ-KS-2"]["attributes"]
    assert summary["notes"]["matrix rows without software items"] == 1
    assert nodes["PREQ-KS-3"]["attributes"]["allocation"] == "N/A"
    assert nodes["PREQ-KS-4"]["attributes"]["unresolved_allocations"] == ["Guidance Engine"]
    assert nodes["PREQ-KS-5"]["attributes"]["unresolved_allocations"] == ["?"]
    assert "" not in nodes["UNIT-Fleet.Ks.Fleet.Api"]["attributes"]["design_sections"]
    rules = yaml.safe_load(Path("specs/rules/document_baseline.yaml").read_text())["rules"]
    unallocated = {f["artifact_id"] for f in evaluate_rules(graph, rules) if f["rule"] == "D01"}
    assert {"PREQ-KS-2", "PREQ-KS-4", "PREQ-KS-5"} <= unallocated


def test_assessability_is_declared_by_sources_not_guessed_from_links(tmp_path) -> None:
    from dhf.ingest.fixtures import ingest_fixtures
    from dhf.trace import gaps

    ado = ingest_fixtures()
    ado["links"] = [e for e in ado["links"] if e["type"] != "verifies"]  # nothing verified
    findings = gaps(ado)
    srs = {a["id"] for a in ado["artifacts"] if a["type"] == "software_req"}
    assert {f["artifact_id"] for f in findings if f["rule"] == "G01"} == srs
    assert "G01" not in unassessable_rules(ado, gap_rules())
    build(tmp_path)
    baseline, _ = import_folder(tmp_path, PROFILE)
    assert {"G01", "G04", "G08"} <= set(unassessable_rules(baseline, gap_rules()))
    assert not [f for f in gaps(baseline) if f["rule"] in ("G01", "G04", "G08")]


def test_external_providers_never_draft_from_company_evidence(tmp_path) -> None:
    import pytest

    from dhf.generate import generate_document
    from dhf.llm import LLM

    class Recorder:
        calls = 0

        def complete(self, *args, **kwargs):
            Recorder.calls += 1
            raise AssertionError("company evidence reached the provider")

    (tmp_path / "docs").mkdir()
    build(tmp_path / "docs")
    (tmp_path / "docs" / "Test_Cases.csv").unlink()  # facts-only packs: no evidence items
    graph, _ = import_folder(tmp_path / "docs", PROFILE)
    llm = LLM("copilotstudio", tmp_path / "llm", Recorder())
    with pytest.raises(ValueError, match="exclusively synthetic"):
        generate_document("sstr", graph, {"release": "1"}, out=tmp_path / "out", llm=llm)
    assert Recorder.calls == 0


def test_explorer_meets_the_dom_harness_contract(tmp_path) -> None:
    import shutil
    import subprocess

    import pytest

    from dhf.ingest.fixtures import ingest_fixtures
    from dhf.render.explorer import create_explorer
    from dhf.trace.consistency import legacy_design

    baseline = legacy_design(Path("data/synthetic/sad_v1.md").read_text())
    html = create_explorer(ingest_fixtures(), [], baselines=[baseline])
    assert "querySelector" not in Path("specs/render/explorer.html").read_text()
    if not shutil.which("node"):
        pytest.skip("node is not installed; the static contract above still applies")
    (tmp_path / "explorer.html").write_text(html)
    check = subprocess.run(
        ["node", "tools/check_explorer.cjs", str(tmp_path / "explorer.html")],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr
