from pathlib import Path

import pytest
import yaml
from mock_ado.state import apply_scenario

from dhf.graph import Store, diff_graph
from dhf.ingest.ado import ADO
from dhf.ingest.code import PythonExtractor
from dhf.ingest.fixtures import ingest_fixtures
from dhf.models.evidence import Artifact


def semantic(graph: dict) -> dict:
    return {
        "artifacts": [
            {**a, "source": {"system": a["source"]["system"], "revision": a["source"]["revision"]}}
            for a in graph["artifacts"]
        ],
        "links": [{k: v for k, v in e.items() if k != "evidence"} for e in graph["links"]],
    }


def test_fixture_http_graph_parity_and_exact_changes(ado_server, tmp_path: Path) -> None:
    ado = ADO(f"http://127.0.0.1:{ado_server.server_port}/kestrel-org", "Kestrel", "mock-app-token")
    try:
        before = ado.ingest(tmp_path / "clones")
        fixtures = ingest_fixtures()
        assert semantic(before) == semantic(fixtures)
        store = Store(tmp_path / "evidence.sqlite")
        first = store.ingest(before)
        assert first["artifacts"] == 248 and first["links"] == 413
        assert store.ingest(before)["changed"] == []
        apply_scenario("change_1", ado_server.root)
        after = ado.ingest(tmp_path / "clones")
        changes = store.ingest(after)
        expected = yaml.safe_load(
            Path("data/synthetic/scenarios/change_1.yaml").read_text(encoding="utf-8")
        )["expected_changed"]
        assert sorted(changes["changed"] + changes["added"]) == sorted(expected)
        assert changes["removed"] == []
        assert store.graph(1) == before
        assert store.last_changes()["changed"] == ["SRS-021", "UNIT-sensor_pressure"]
        store.close()
        reopened = Store(tmp_path / "evidence.sqlite")
        assert reopened.graph() == after
        reopened.close()
        assert all(
            a["source"]["retrieved_at"] and len(a["content_hash"]) == 64 for a in after["artifacts"]
        )
    finally:
        ado.close()


def test_source_write_rejected_without_http() -> None:
    ado = ADO(token="mock-app-token")
    with pytest.raises(ValueError, match="forbids"):
        ado.request("PATCH", "/_apis/wit/workitems/1", {})
    ado.close()


def test_hash_integrity_and_link_only_changes() -> None:
    data = ingest_fixtures()
    tampered = {**data["artifacts"][0], "body": "tampered"}
    with pytest.raises(ValueError, match="hash mismatch"):
        Artifact.model_validate(tampered)
    current = {**data, "links": data["links"][1:]}
    assert data["links"][0]["src"] in diff_graph(data, current)["changed"]


def test_ast_extractor_real_data_not_synthetic() -> None:
    data = PythonExtractor().extract(
        {"kestrel/real.py": "# DHF-COMPONENT: COMP-01\ndef sample(a: int) -> int:\n    return a\n"},
        "git://real",
        "2026-10-12T00:00:00Z",
    )
    assert data["artifacts"][0]["attributes"]["synthetic"] is False
    assert data["artifacts"][0]["attributes"]["signatures"] == ["def sample(a: int) -> int"]


def test_metadata_stripped_equivalent_graph(ado_server, tmp_path: Path) -> None:
    from mock_ado.state import read_state, write_state

    ado = ADO(f"http://127.0.0.1:{ado_server.server_port}/kestrel-org", "Kestrel", "mock-app-token")
    try:
        before = ado.ingest(tmp_path / "clones")
        state = read_state(ado_server.root)
        for entry in state["items"].values():
            for item in [entry["current"], *entry["history"]]:
                item["fields"]["System.Description"] = item["fields"]["System.Description"].split(
                    "\nDHF-META:", 1
                )[0]
        for run in state["runs"]:
            run["comment"] = run["comment"].split("\nDHF-META:", 1)[0]
            for result in run["results"]:
                result["comment"] = result["comment"].split("\nDHF-META:", 1)[0]
        write_state(ado_server.root, state)
        after = ado.ingest(tmp_path / "clones")
        assert semantic(before) == semantic(after)
        srs = next(a for a in after["artifacts"] if a["id"] == "SRS-021")
        assert srs["attributes"]["component"] == "COMP-03"
        assert "80 kPa" in srs["attributes"]["acceptance_criteria"]
        hazard = next(a for a in after["artifacts"] if a["id"] == "HAZ-01")
        assert hazard["attributes"]["severity"] == 5
        assert all("verified_revision" not in a["attributes"] for a in after["artifacts"])
    finally:
        ado.close()


def test_enriched_fixture_quality_and_native_revision_history() -> None:
    graph = ingest_fixtures()
    nodes = {a["id"]: a for a in graph["artifacts"]}
    assert nodes["HAZ-01"]["attributes"]["severity"] == 5
    assert nodes["HAZ-05"]["attributes"]["severity"] == 5
    for a in nodes.values():
        if a["type"] == "software_req":
            assert a["body"] != a["attributes"]["acceptance_criteria"]
            assert len(a["body"]) > 100
        if a["type"] == "test_case":
            assert a["attributes"]["steps"][0]["action"]
            assert a["attributes"]["steps"][0]["expected"]
        if a["type"] == "hazard":
            assert all(
                term in a["body"] for term in ("Foreseeable harm:", "Cause sequence:", "Severity")
            )
        if a["type"] == "defect":
            assert a["attributes"]["severity"] and "Impact assessment:" in a["body"]
    assert nodes["SRS-030"]["attributes"]["requirement_history"] == [
        {"revision": 1, "changed_at": "2026-09-20T12:00:00Z"},
        {"revision": 2, "changed_at": "2026-10-04T12:00:00Z"},
    ]
    assert len(Path("data/synthetic/prd.md").read_text(encoding="utf-8").split()) >= 200
    assert len(Path("data/synthetic/sad_v1.md").read_text(encoding="utf-8").split()) >= 400
    for name in (
        "sensor_pressure",
        "infusion_bounds",
        "alarm_latch",
        "drug_limits",
        "sensor_air",
        "sensor_filter",
        "sensor_calibration",
        "infusion_motor",
        "infusion_volume",
        "alarm_priority",
        "alarm_audio",
        "drug_lookup",
        "comms_frame",
        "comms_timeout",
        "log_events",
        "log_digest",
    ):
        count = len(
            Path(f"data/synthetic/code/kestrel/{name}.py").read_text(encoding="utf-8").splitlines()
        )
        assert 30 <= count <= 120, (name, count)
