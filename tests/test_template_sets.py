"""Template sets: the owner's document structure over the same evidence pipeline."""

from pathlib import Path

import pytest

from dhf.generate import generate_document, load_spec
from dhf.impact import impact, read_sections, regenerate
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM

OWNER_SSTR = [
    "# Software System Test Report (SSTR)",
    "## Introduction/Purpose",
    "## Plan Execution Summary",
    "### Scope",
    "### Readiness Reviews",
    "### Test Environments",
    "### Software System Test Types Used",
    "### Tools Analysis",
    "## Deliverables",
    "### Traceability",
    "### Documents",
    "## Test Execution Summary",
    "### Software System Test Case Results",
    "### Failed Tests and Anomaly Assessment",
    "### Multiple Test Executions",
    "### Summary by Build",
    "### Third Party For Security Testing",
    "### Non-Requirement Testing",
    "### Known Residual Anomalies",
    "### Verification Coverage Gaps",
    "## Conclusion",
    "## Evidence Index",
    "## Version History",
    "## Approvals",
]


def headings(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("#")]


def body(markdown: str, section: str) -> str:
    """Section text without its headings, for comparing content across structures."""
    lines = read_sections(markdown)[section].splitlines()
    return "\n".join(line for line in lines if line.strip() and not line.startswith("#"))


def test_owner_template_set_reuses_sections_under_the_owner_structure(tmp_path, monkeypatch):
    graph = ingest_fixtures()
    default = generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path / "a", llm=LLM(root=tmp_path / "llm")
    )
    monkeypatch.setenv("DHF_TEMPLATE_SET", "bd")
    owner = generate_document(
        "sstr", graph, {"release": "1.1"}, out=tmp_path / "b", llm=LLM(root=tmp_path / "llm")
    )
    assert headings(owner["markdown"]) == OWNER_SSTR
    assert owner["manifest"]["template_spec"]["path"] == "specs/documents/bd/sstr.yaml"
    assert default["manifest"]["template_spec"]["path"] == "specs/documents/sstr.yaml"
    for shared in ("results_summary", "results_by_requirement", "test_environment"):
        assert body(owner["markdown"], shared) == body(default["markdown"], shared)
    modes = {s["id"]: s["mode"] for s in load_spec("sstr")["sections"]}
    assert modes["readiness_reviews"] == "human" and modes["release_conclusion"] == "ai"


def test_regeneration_keeps_the_recorded_template(tmp_path, monkeypatch):
    graph = ingest_fixtures()
    monkeypatch.setenv("DHF_TEMPLATE_SET", "bd")
    llm = LLM(root=tmp_path / "llm")
    first = generate_document("sstr", graph, {"release": "1.1"}, out=tmp_path, llm=llm)
    monkeypatch.delenv("DHF_TEMPLATE_SET")
    report = impact(graph, first["manifest"], graph)
    again = regenerate(graph, first["manifest"], first["markdown"], report, tmp_path, llm)
    assert headings(again["markdown"]) == OWNER_SSTR
    assert again["manifest"]["template_spec"]["path"] == "specs/documents/bd/sstr.yaml"


def test_template_names_are_validated(monkeypatch):
    monkeypatch.setenv("DHF_TEMPLATE_SET", "../../etc")
    with pytest.raises(ValueError, match="template set"):
        load_spec("sstr")
    monkeypatch.setenv("DHF_TEMPLATE_SET", "bd")
    assert load_spec("sfmea") == load_spec("sfmea", "specs/documents/sfmea.yaml")  # no variant
    with pytest.raises(ValueError, match="recorded template"):
        load_spec("sstr", "specs/documents/bd/sad.yaml")
    assert Path("specs/documents/bd/sstr.yaml").exists()


def test_owner_sad_and_sdd_nest_items_and_units_like_the_owner_documents(tmp_path, monkeypatch):
    monkeypatch.setenv("DHF_TEMPLATE_SET", "bd")
    graph = ingest_fixtures()
    sad = generate_document("sad", graph, {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path))
    outline = headings(sad["markdown"])
    top = [h for h in outline if h.startswith("## ")]
    assert top == [
        "## Introduction",
        "## Architecture Overview",
        "## Software Architecture Description",
        "## Software Item Design",
        "## Hardware or Software Environment",
        "## Requirements Matrix",
        "## Open Design and Verification Gaps",
        "## Additional Open Issues and Dispositions",
        "## Version History",
    ]
    item = outline.index("### COMP-01: UI")
    assert outline[item + 1 : item + 3] == [
        "#### Responsibilities and Collaborators",
        "#### Allocated Requirements",
    ]
    sdd = generate_document("sdd", graph, {"release": "1.1"}, out=tmp_path, llm=LLM(root=tmp_path))
    outline = headings(sdd["markdown"])
    units = [h for h in outline if h.startswith("### UNIT-")]
    first = outline.index(units[0])
    assert len(units) == 20 and outline[first + 1 : first + 7] == [
        "#### Unit Identification",
        "#### Software Unit Description",
        "#### Interface",
        "#### Internal Structure",
        "#### Processing Logic",
        "#### Error Handling",
    ]
