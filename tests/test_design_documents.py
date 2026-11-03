"""SAD and SDD without code: the architecture comes from design documents (ADR-044)."""

from pathlib import Path

import pytest
import yaml
from docx import Document
from mock_ado.state import read_state

from dhf.generate import generate_document
from dhf.graph.design import design_query
from dhf.ingest.ado import ADO, load_scope
from dhf.ingest.documents import import_folder, merge_baseline
from dhf.llm import LLM
from dhf.models.values import opening_sentence
from dhf.render.diagram import diagram_bytes, diagram_layout, fit

PROFILE = Path("specs/doc_import/dhf_documents.yaml")


def table(document, rows: list[list[str]]) -> None:
    grid = document.add_table(rows=len(rows), cols=len(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            grid.cell(r, c).text = value


def design_documents(folder: Path, matrix: list[list[str]]) -> None:
    """A two-item architecture with its allocation matrix and one item's detailed design."""
    folder.mkdir(parents=True, exist_ok=True)
    sad = Document()
    sad.add_heading("Software Item Design", 1)
    sad.add_heading("Sensor Monitoring", 2)
    sad.add_paragraph("Description")
    sad.add_paragraph("Samples line pressure and raises occlusion events. Runs every cycle.")
    sad.add_heading("Event Log", 2)
    sad.add_paragraph("Keeps the event history.")
    sad.add_heading("Requirements Matrix", 1)
    table(sad, [["Req. ID", "Software Items"], *matrix])
    sad.save(folder / "Pump Software Architecture Document_v02.docx")
    sdd = Document()
    sdd.add_heading("Detailed Design", 1)
    sdd.add_heading("Sensor Monitoring", 2)
    sdd.add_heading("Ks.Sensor.Filter", 3)
    sdd.add_heading("Software Unit Description", 4)
    sdd.add_paragraph("Filters raw pressure samples.")
    for name in ("Processing Logic", "Error Handling"):
        sdd.add_heading(name, 4)
        sdd.add_paragraph(f"Filter {name.lower()}.")
    sdd.save(folder / "Pump SDD - Sensor Monitoring_v01.docx")
    prd = Document()  # requirements stay ADO's: documents must not add these
    table(
        prd,
        [["Req ID", "Short Text", "Requirement Text"], ["PREQ-PM-7", "Need", "It shall hold."]],
    )
    prd.save(folder / "Pump PRD #2.docx")


def test_sad_and_sdd_draft_from_design_documents_without_code(tmp_path) -> None:
    design_documents(tmp_path / "docs", [["PREQ-PM-7", "Sensor Monitoring"]])
    graph, _ = import_folder(tmp_path / "docs", PROFILE)
    rows = design_query(graph, "components", {})["facts"]["rows"]
    assert {r["name"]: r["responsibility"] for r in rows} == {
        "Event Log": "Keeps the event history.",
        "Sensor Monitoring": "Samples line pressure and raises occlusion events.",
    }
    assert {r["safety_class"] for r in rows} == {"Not recorded in the source"}
    llm = LLM("mock", root=tmp_path / "llm")
    sad = generate_document("sad", graph, {"release": "1"}, "mock", out=tmp_path / "out", llm=llm)
    sdd = generate_document("sdd", graph, {"release": "1"}, "mock", out=tmp_path / "out", llm=llm)
    assert "SI-Sensor-Monitoring" in sad["markdown"] and "Event Log" in sad["markdown"]
    unit = "UNIT-Sensor-Monitoring.Ks.Sensor.Filter"
    interfaces = next(s for s in sdd["manifest"]["sections"] if s["id"] == "interfaces." + unit)
    # No versioned file name in the facts: re-issuing the document stales nothing.
    assert interfaces["facts"]["notice"] == (
        "No code is in scope; the interface is described in the design document under "
        "Detailed Design > Sensor Monitoring > Ks.Sensor.Filter."
    )
    assert "SI-Sensor-Monitoring" in (tmp_path / "out" / "sad.architecture.mmd").read_text()
    # System requirements the architecture allocates appear in the SAD allocation tables.
    allocation = design_query(graph, "component_allocation", {"entity": "SI-Sensor-Monitoring"})[
        "facts"
    ]["rows"]
    assert [r["requirement"] for r in allocation] == ["PREQ-PM-7"]
    matrix = design_query(graph, "architecture_matrix", {})["facts"]["rows"]
    assert {r["requirement"]: r["components"] for r in matrix}["PREQ-PM-7"] == [
        "SI-Sensor-Monitoring"
    ]
    # A safety analysis never silently drops an item whose class is unknown.
    from dhf.generate import expand_sections, load_spec

    with pytest.raises(ValueError, match="needs a recorded safety class"):
        expand_sections(load_spec("sfmea"), graph)


def test_ado_ingest_takes_the_architecture_from_the_scope_documents(ado_server, tmp_path):
    ids = read_state(ado_server.root)["ids"]
    design_documents(
        tmp_path / "docs",
        [["SRS-021", "Sensor Monitoring"], ["SRS-404", "Event Log"], ["PREQ-PM-7", "Event Log"]],
    )
    (tmp_path / "docs" / "Pump SDD - Broken_v01.docx").write_bytes(b"not a Word package")
    scope_file = tmp_path / "scope.yaml"
    scope_file.write_text(
        yaml.safe_dump(
            {
                "seed_ids": [ids["SRS-021"]],
                "follow": {"depth": 0},
                "history": False,
                "repository": "",
                "documents": "docs",
            }
        )
    )
    scope = load_scope(str(scope_file))
    assert scope["documents"]["folder"] == str(tmp_path / "docs")
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope)
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    nodes = {a["id"]: a for a in graph["artifacts"]}
    links = {(e["src"], e["dst"]) for e in graph["links"] if e["type"] == "allocated_to"}
    assert {"SI-Sensor-Monitoring", "SI-Event-Log"} <= set(nodes)
    assert "PREQ-PM-7" not in nodes  # requirements come from ADO only
    # The matrix row links the ADO requirement although no document lists it.
    assert ("SRS-021", "SI-Sensor-Monitoring") in links
    assert ("UNIT-Sensor-Monitoring.Ks.Sensor.Filter", "SI-Sensor-Monitoring") in links
    assert nodes["SRS-021"]["source"]["system"] == "ado"
    assert "allocated_to" in nodes["SRS-021"]["attributes"]["link_classes"]
    assert ado.report["design documents read"] == 3
    assert ado.report["design documents: unreadable documents"] == 1  # never silent
    assert ado.report["design documents: matrix rows for unknown requirements"] == 1  # SRS-404
    assert ado.report["document links to items outside the scope"] == 1  # PREQ-PM-7


def test_merge_keeps_ado_authoritative_for_shared_ids() -> None:
    def artifact(id: str, kind: str, system: str) -> dict:
        source = {"system": system, "url": "x", "native_id": id, "revision": "1"}
        return {"id": id, "type": kind, "title": id, "body": system, "attributes": {}} | {
            "source": source | {"retrieved_at": "2026-11-03T00:00:00Z"}
        }

    ado = {"artifacts": [artifact("SRS-1", "software_req", "ado")], "links": []}
    docs = {
        "artifacts": [
            artifact("SRS-1", "software_req", "file"),
            artifact("SI-A", "component", "file"),
        ],
        "links": [
            {"src": "SRS-1", "dst": "SI-A", "type": "allocated_to", "origin": "explicit"}
            | {"evidence": "matrix"}
        ],
    }
    merged, report = merge_baseline(ado, docs, ["component", "software_unit"], [])
    assert [a["body"] for a in merged["artifacts"] if a["id"] == "SRS-1"] == ["ado"]
    assert len(merged["links"]) == 1 and report["document component added"] == 1


def test_documents_are_checked_when_an_ingest_starts_not_when_ado_is_opened(tmp_path):
    scope_file = tmp_path / "scope.yaml"
    scope_file.write_text(yaml.safe_dump({"seed_ids": [1], "documents": "missing"}))
    scope = load_scope(str(scope_file))  # commands that never ingest still work
    unreachable = "http://127.0.0.1:9/org"  # any ADO read would fail to connect
    ado = ADO(unreachable, "P", "mock-app-token", scope=scope)
    try:
        with pytest.raises(ValueError, match="documents folder not found"):
            ado.ingest(tmp_path / "clones")
        (tmp_path / "missing").mkdir()
        ado.scope["documents"]["profile"] = str(tmp_path / "typo.yaml")
        with pytest.raises(ValueError, match="documents profile not found"):
            ado.ingest(tmp_path / "clones")
    finally:
        ado.close()


def test_component_diagram_lays_out_documented_architectures() -> None:
    names = [f"SI_Item{i}" for i in range(14)]
    lines = ["flowchart LR"] + [f'  {n}["{n}: Item {i}"]' for i, n in enumerate(names)]
    for i in range(7):
        unit = f"UNIT_Item0_Ks_FleetMonitorService_Part{i}"
        lines += [
            f'  {unit}["UNIT-x: Software Unit: Ks.FleetMonitorService.Part{i}"]',
            f"  {unit} -->|allocated to| SI_Item0",
        ]
    layout = diagram_layout("\n".join(lines))
    assert len(layout["components"]) == 14 and layout["box_height"] == 97 + 7 * 27
    assert layout["components"][0]["units"][0] == "K.F.Part0"  # distinct, fits one line
    assert diagram_bytes("\n".join(lines)).startswith(b"\x89PNG")
    # The synthetic six-component layout keeps its original geometry.
    kestrel = ["flowchart LR"] + [f'  COMP_0{i}["COMP-0{i}: C{i}"]' for i in range(1, 7)]
    assert diagram_layout("\n".join(kestrel))["box_height"] == 235
    assert fit("Short name") == "Short name"
    assert fit("Ks.Svc.TemperatureSensorReaderPrimary") != fit("Ks.Svc.TemperatureSensorReaderB")
    assert opening_sentence("Description\nKeeps logs. More.") == "Keeps logs."
    assert opening_sentence("Description:\nKeeps logs, e.g. alarms. More.") == (
        "Keeps logs, e.g. alarms."
    )
    assert opening_sentence("Interface | Direction | Peer | Data\nSends events.") == (
        "Sends events."
    )
    # Long unit lists are capped, units without an item are counted, and a reviewer's
    # unit-to-unit edge in the Mermaid block never breaks the Word render.
    many = lines + [
        '  UNIT_z["UNIT-z: Loose"]',
        "  UNIT_z -->|calls| UNIT_Item0_Ks_FleetMonitorService_Part0",
    ]
    big = diagram_layout(
        "\n".join(many + [f"  UNIT_{i} -->|allocated to| SI_Item1" for i in range(30)])
    )
    assert big["unplaced"] == 1 and big["dependencies"] == []
    assert len(next(c for c in big["components"] if c["id"] == "SI_Item1")["units"]) <= 10
    assert diagram_bytes("\n".join(many)).startswith(b"\x89PNG")


def test_a_scope_change_is_reported_as_one_and_still_reflags_drafts(tmp_path) -> None:
    from dhf.graph import Store, configuration_only

    def graph(classes: list[str]) -> dict:
        source = {"system": "ado", "url": "x", "native_id": "1", "revision": "3"}
        artifact = {"id": "SRS-1", "type": "software_req", "title": "t", "body": "b"}
        return {
            "artifacts": [
                artifact
                | {"attributes": {"link_classes": classes}}
                | {"source": source | {"retrieved_at": "2026-11-03T00:00:00Z"}}
            ],
            "links": [],
        }

    store = Store(tmp_path / "evidence.sqlite")
    try:
        store.ingest(graph(["verifies"]))
        before = store.graph()["artifacts"][0]
        # Assessability can change with the scope, so drafts citing it are re-flagged.
        assert store.ingest(graph(["allocated_to", "verifies"]))["changed"] == ["SRS-1"]
        after = store.graph()["artifacts"][0]
    finally:
        store.close()
    assert configuration_only(before, after)
    edited = after | {"body": "changed text"}
    assert not configuration_only(before, edited)


def test_document_names_keep_issue_markers_and_design_data_errors_surface() -> None:
    from dhf.graph.reviews import risk_rows
    from dhf.ingest.documents import document_of

    url = "file:Pump SDD #3 - Sensor Monitoring.docx?sha256=abc123#unit-1"
    assert document_of({"source": {"url": url}}) == "Pump SDD #3 - Sensor Monitoring.docx"

    def artifact(id: str, kind: str, attributes: dict) -> dict:
        source = {"system": "git", "url": "x", "native_id": id, "revision": "1"}
        return {"id": id, "type": kind, "title": id, "body": "b", "attributes": attributes} | {
            "source": source | {"retrieved_at": "2026-11-03T00:00:00Z"}
        }

    graph = {
        "artifacts": [
            artifact("UNIT-a", "software_unit", {"component": "COMP-99", "path": "a.py"}),
            artifact("HAZ-1", "hazard", {}),  # ADO omits an empty Severity field
        ],
        "links": [],
    }
    with pytest.raises(ValueError, match="COMP-99, which is not in evidence"):
        design_query(graph, "unit_identity", {"entity": "UNIT-a"})
    rows = design_query(graph, "architecture_risks", {})["facts"]["rows"]
    assert rows[0]["severity"] == "Not recorded in the source"
    assert risk_rows(graph)[0]["severity"] == "Not recorded in the source"


def test_documented_design_text_and_allocations_are_evidence(tmp_path) -> None:
    from dhf.propose import proposal_jobs

    design_documents(tmp_path / "docs", [["PREQ-PM-7", "Sensor Monitoring"]])
    graph, _ = import_folder(tmp_path / "docs", PROFILE)
    unit = next(a for a in graph["artifacts"] if a["type"] == "software_unit")
    assert unit["attributes"]["design_text"] == {
        "Processing Logic": "Filter processing logic.",
        "Error Handling": "Filter error handling.",
    }
    # An edit to error handling that keeps the word count is still an evidence change.
    sdd = tmp_path / "docs" / "Pump SDD - Sensor Monitoring_v01.docx"
    document = Document(sdd)
    paragraph = next(p for p in document.paragraphs if p.text == "Filter error handling.")
    paragraph.text = "Filter error dropping."
    document.save(sdd)
    edited, _ = import_folder(tmp_path / "docs", PROFILE)
    after = next(a for a in edited["artifacts"] if a["id"] == unit["id"])
    assert after["content_hash"] != unit["content_hash"]
    # Units from documents cannot record implementing code, so no orphan-code proposals.
    assert not [job for job in proposal_jobs(graph, []) if job["id"].startswith("L02.")]


def test_documented_items_reach_risk_evidence_through_their_allocation() -> None:
    def artifact(id: str, kind: str, system: str = "ado") -> dict:
        source = {"system": system, "url": "x", "native_id": id, "revision": "1"}
        return {"id": id, "type": kind, "title": id, "body": "b", "attributes": {}} | {
            "source": source | {"retrieved_at": "2026-11-03T00:00:00Z"}
        }

    def link(src: str, dst: str, kind: str) -> dict:
        return {"src": src, "dst": dst, "type": kind, "origin": "explicit", "evidence": "x"}

    graph = {
        "artifacts": [
            artifact("SI-Pump", "component", "file"),
            artifact("SPEC-1", "software_req"),
            artifact("RC-1", "risk_control"),
            artifact("HAZ-1", "hazard"),
        ],
        "links": [
            link("SPEC-1", "SI-Pump", "allocated_to"),
            link("SPEC-1", "RC-1", "implements"),
            link("RC-1", "HAZ-1", "mitigates"),
        ],
    }
    facts = design_query(graph, "component_design", {"entity": "SI-Pump"})["facts"]
    assert facts["hazard_controls"] == [{"hazard": "HAZ-1", "title": "HAZ-1", "controls": ["RC-1"]}]
