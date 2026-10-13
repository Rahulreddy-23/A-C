from pathlib import Path

from dhf.generate import expand_sections, generate_document, load_spec
from dhf.graph.queries import query
from dhf.ingest.fixtures import ingest_fixtures
from dhf.llm import LLM
from dhf.trace.consistency import component_consistency


def test_all_components_units_allocations_and_local_diagrams(tmp_path: Path) -> None:
    graph = ingest_fixtures()
    llm = LLM(root=tmp_path / "llm")
    sad = generate_document("sad", graph, {"release": "1.1"}, out=tmp_path, llm=llm)
    sdd = generate_document("sdd", graph, {"release": "1.1"}, out=tmp_path, llm=llm)
    components = {a["id"] for a in graph["artifacts"] if a["type"] == "component"}
    units = {a["id"] for a in graph["artifacts"] if a["type"] == "software_unit"}
    assert len(components) == 6 and len(units) == 20
    assert component_consistency(graph, [sad["manifest"], sdd["manifest"]]) == []
    for result in (sad, sdd):
        assert components <= set(result["manifest"]["component_set"])
        assert not [s for s in result["manifest"]["sections"] if s["status"] == "ai_unavailable"]
    assert all(id in sdd["markdown"] for id in units)
    assert len(expand_sections(load_spec("sdd"), graph)) == 162
    diagram = (tmp_path / "sad.architecture.mmd").read_text()
    assert diagram.startswith("flowchart LR") and "UNIT_sensor_pressure -->" in diagram
    assert all(id.replace("-", "_") in diagram for id in components | units)
    pressure = query(graph, "unit_allocation", {"entity": "UNIT-sensor_pressure"})
    assert {r["requirement"] for r in pressure["facts"]["rows"]} == {
        "SRS-003",
        "SRS-009",
        "SRS-015",
        "SRS-021",
        "SRS-022",
        "SRS-023",
        "SRS-027",
        "SRS-033",
    }
    interfaces = query(graph, "unit_interfaces", {"entity": "UNIT-sensor_pressure"})
    assert any("evaluate" in r["signature"] for r in interfaces["facts"]["rows"])
    soup = query(graph, "soup_inventory", {})
    assert len(soup["facts"]["rows"]) == 5
    assert soup["facts"]["rows"][0]["version"] == "24.2.0"
    edited = {**sad["manifest"], "component_set": sorted(components - {"COMP-06"})}
    assert component_consistency(graph, [edited])[0]["missing"] == ["COMP-06"]
