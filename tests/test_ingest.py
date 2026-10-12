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
        assert first["artifacts"] == 248 and first["links"] == 473
        assert store.ingest(before)["changed"] == []
        apply_scenario("change_1", ado_server.root)
        after = ado.ingest(tmp_path / "clones")
        changes = store.ingest(after)
        expected = yaml.safe_load(Path("data/synthetic/scenarios/change_1.yaml").read_text())[
            "expected_changed"
        ]
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


def test_source_write_rejected_without_http(tmp_path: Path) -> None:
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
