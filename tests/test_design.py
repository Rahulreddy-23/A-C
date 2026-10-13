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
    assert (
        "### Purpose" in sdd["markdown"]
        and "## UNIT-sensor_pressure: sensor_pressure" in sdd["markdown"]
    )
    assert "| Name | Kind / bases | Fields |" in sdd["markdown"]
    assert "G12" in sad["markdown"] and "SOUP-01" in sad["markdown"]
    assert len(expand_sections(load_spec("sdd"), graph)) == 162
    diagram = (tmp_path / "sad.architecture.mmd").read_text()
    assert diagram.startswith("flowchart LR") and "UNIT_sensor_pressure -->" in diagram
    assert all(id.replace("-", "_") in diagram for id in components | units)
    pressure = query(graph, "unit_allocation", {"entity": "UNIT-sensor_pressure"})
    assert {r["requirement"] for r in pressure["facts"]["rows"]} == {"SRS-009", "SRS-021"}
    interfaces = query(graph, "unit_interfaces", {"entity": "UNIT-sensor_pressure"})
    assert any("evaluate" in r["signature"] for r in interfaces["facts"]["rows"])
    soup = query(graph, "soup_inventory", {})
    assert len(soup["facts"]["rows"]) == 5
    assert soup["facts"]["rows"][0]["version"] == "24.2.0"
    edited = {**sad["manifest"], "component_set": sorted(components - {"COMP-06"})}
    assert component_consistency(graph, [edited])[0]["missing"] == ["COMP-06"]


def test_design_structure_and_extracted_dependency():
    graph = ingest_fixtures()
    pack = query(graph, "runtime_view", {"release": "1.1"})
    assert len(pack["facts"]["unit_allocation"]) == 20
    assert pack["facts"]["dependencies"] == [
        {
            "from_unit": "UNIT-sensor_pressure",
            "to_unit": "UNIT-alarm_latch",
            "from_component": "COMP-03",
            "to_component": "COMP-04",
            "call": "kestrel.alarm_latch.latched",
        }
    ]
    assert (
        "kestrel.alarm_latch.latched"
        in query(graph, "architecture_diagram", {})["facts"]["diagram"]
    )
    assert len({a["body"] for a in graph["artifacts"] if a["type"] == "component"}) == 6
    component = query(graph, "component_design", {"entity": "COMP-03"})
    assert {u["unit"] for u in component["facts"]["unit_allocation"]} == {
        "UNIT-sensor_pressure",
        "UNIT-sensor_air",
        "UNIT-sensor_calibration",
        "UNIT-sensor_filter",
    }


def test_every_ai_fact_id_is_in_the_evidence_pack():
    from dhf.llm import canonical
    from dhf.models.values import ID_PATTERN

    graph = ingest_fixtures()
    for doc in ("sad", "sdd", "sstr", "sfmea", "drr"):
        for section in expand_sections(load_spec(doc), graph):
            if section["mode"] != "ai":
                continue
            params = {
                "release": "1.1",
                **({"entity": section["entity"]} if section.get("entity") else {}),
            }
            pack = query(graph, section["query"], params)
            assert {id.rstrip(".") for id in ID_PATTERN.findall(canonical(pack["facts"]))} <= {
                a["id"] for a in pack["evidence"]
            }, section["id"]


def test_synthesis_reduction_keeps_fact_references():
    import copy

    from dhf.generate import reduce_synthesis
    from dhf.graph.queries import prompt_pack
    from dhf.llm import canonical
    from dhf.models.values import ID_PATTERN

    source = query(ingest_fixtures(), "failed_results_with_defects", {"release": "1.1"})
    # Force the adverse-result priority path to omit ordinary narrative context.
    context = query(ingest_fixtures(), "component_design", {"entity": "COMP-03"})
    source["evidence"] = list(
        {a["id"]: a for a in [*source["evidence"], *context["evidence"]]}.values()
    )
    source["facts"]["related_context"] = context["facts"]
    model = copy.deepcopy(prompt_pack(source))
    for a in model["evidence"]:
        a["body"] += " Context remains source data." * 1500
    reduced, audit = reduce_synthesis(model, source, 12000)
    assert audit["reduced"] and audit["compact_context_ids"]
    assert {id.rstrip(".") for id in ID_PATTERN.findall(canonical(reduced["facts"]))} <= {
        a["id"] for a in reduced["evidence"]
    }


def test_section_tiers_and_model_provenance(tmp_path):
    from dhf.generate import generate_section
    from dhf.llm import LLM
    from dhf.propose import proposal_jobs

    graph = ingest_fixtures()
    llm = LLM(root=tmp_path)
    for doc in ("sstr", "sad", "sdd", "sfmea", "drr"):
        for section in expand_sections(load_spec(doc), graph):
            if section["mode"] != "ai":
                continue
            expected = (
                "analytical"
                if (doc in ("sfmea", "drr") or section["id"] == "release_conclusion")
                else "default"
            )
            assert section.get("model_tier", "default") == expected
    section = next(s for s in load_spec("sstr")["sections"] if s["id"] == "release_conclusion")
    result = generate_section(section, graph, {"release": "1.1"}, llm)
    assert result["model"] == {"provider": "mock", "name": "mock-v2", "tier": "analytical"}
    assert {j["model_tier"] for j in proposal_jobs(graph, [])} == {"analytical"}
