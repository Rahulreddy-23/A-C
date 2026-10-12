from pathlib import Path
from zipfile import ZipFile

from lxml import etree
from mock_ado.state import apply_scenario

from dhf.generate import generate_document, reduce_synthesis
from dhf.graph.queries import prompt_pack, query
from dhf.ingest.ado import ADO
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.llm.tokens import estimate_tokens
from dhf.render import paragraph_diff, render_docx, visible

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def test_link_destination_only_change_has_no_redline(tmp_path: Path) -> None:
    before = (
        "# Title\n\nSee [SRS-021](http://localhost/old).\n\n"
        "| Requirement | Rev |\n|---|---|\n"
        "| [SRS-021](http://localhost/old) | 1 |\n"
    )
    after = before.replace("/old", "/new")
    path = tmp_path / "links.docx"
    counts = render_docx(after, path, before, "2026-10-12T00:00:00Z")
    assert counts == {"insertions": 0, "deletions": 0, "comments": 0}
    with ZipFile(path) as archive:
        assert b"http://localhost/new" in archive.read("word/_rels/document.xml.rels")
        assert b"http://localhost/old" not in archive.read("word/_rels/document.xml.rels")


def test_deterministic_synthesis_reduction_keeps_critical_evidence() -> None:
    pack = query(ingest_fixtures(), "release_readiness_facts", {"release": "1.1"})
    model = prompt_pack(pack)
    for item in model["evidence"]:
        item["body"] *= 100
    reduced, audit = reduce_synthesis(model, pack, 2000)
    original_nodes = {a["id"]: a for a in pack["evidence"]}
    critical = {
        a["id"]
        for a in pack["evidence"]
        if a["type"] == "defect"
        or (a["type"] == "test_result" and a["attributes"]["outcome"] in ("Failed", "Blocked"))
    }
    assert critical <= {a["id"] for a in reduced["evidence"]}
    assert audit["reduced"] and audit["excerpted_ids"]
    assert estimate_tokens(__import__("json").dumps(reduced)) <= 2000
    assert reduced["facts"]["gap_findings"] == pack["facts"]["gap_findings"]
    assert all(
        original_nodes[id]["type"] not in ("defect", "test_result")
        for id in audit["omitted_context_ids"]
    )
    assert reduce_synthesis(model, pack, 2000) == (reduced, audit)


def test_change_1_regeneration_and_redline_are_confined(ado_server, tmp_path: Path) -> None:
    ado = ADO(f"http://127.0.0.1:{ado_server.server_port}/kestrel-org")
    llm = LLM(root=tmp_path / "llm")
    try:
        before_graph = ado.ingest(tmp_path / "clones")
        before = generate_document(
            "sstr", before_graph, {"release": "1.1"}, out=tmp_path / "before", llm=llm
        )
        apply_scenario("change_1", ado_server.root)
        after_graph = ado.ingest(tmp_path / "clones")
        after = generate_document(
            "sstr", after_graph, {"release": "1.1"}, out=tmp_path / "after", llm=llm
        )
    finally:
        ado.close()
    assert all(s["status"] != "ai_unavailable" for s in after["manifest"]["sections"])
    summaries = [
        next(s for s in r["manifest"]["sections"] if s["id"] == "results_summary")["facts"][
            "summary"
        ]
        for r in (before, after)
    ]
    assert [(s["passed"], s["failed"]) for s in summaries] == [(39, 1), (38, 2)]
    result = render_docx(
        after["markdown"], tmp_path / "redline.docx", before["markdown"], "2026-10-12T00:00:00Z"
    )
    with ZipFile(tmp_path / "redline.docx") as archive:
        xml = etree.fromstring(archive.read("word/document.xml"))
    paragraphs = xml.xpath("//w:p", namespaces=NS)
    changed = xml.xpath("//w:p[.//w:ins or .//w:del]", namespaces=NS)
    assert len(changed) / len(paragraphs) < 0.1
    assert result["insertions"] + result["deletions"] < 80
    changed_cells = xml.xpath("//w:tc[.//w:ins or .//w:del]", namespaces=NS)
    changed_rows = xml.xpath("//w:tr[.//w:ins or .//w:del]", namespaces=NS)
    for cell in changed_cells:
        row_text = "".join(
            cell.getparent().xpath(".//w:t/text()|.//w:delText/text()", namespaces=NS)
        )
        assert any(
            id in row_text
            for id in ("SRS-021", "UNIT-sensor_pressure", "RUN-3", "RES-3-021", "TC-021")
        ) or ("39" in row_text and "38" in row_text)
    allowed = {
        "references",
        "results_summary",
        "results_by_requirement",
        "anomaly_assessment",
        "retest_results",
        "verification_gaps",
        "release_conclusion",
        "evidence_index",
    }
    before_sections = {s["id"]: s for s in before["manifest"]["sections"]}
    for section in after["manifest"]["sections"]:
        if section["id"] not in allowed:
            assert section["markdown"] == before_sections[section["id"]]["markdown"]
    # Every non-table visible change belongs to one of the expected AI sections.
    changes = paragraph_diff(before["markdown"], after["markdown"])
    ai_text = "\n".join(
        s["markdown"]
        for r in (before, after)
        for s in r["manifest"]["sections"]
        if s["id"] in ("anomaly_assessment", "release_conclusion")
    )
    for item in changes:
        if item["change"] != "equal" and item["block"]["type"] != "table":
            assert visible(item["block"]["text"]) in visible(ai_text)
    total_rows = len(xml.xpath("//w:tr", namespaces=NS))
    print(
        f"redline: {len(changed)}/{len(paragraphs)} paragraphs; "
        f"{len(changed_rows)}/{total_rows} rows; {result}"
    )
