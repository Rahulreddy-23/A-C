import copy
import threading

import httpx
import pytest
from mock_ado.server import Server
from mock_ado.state import read_state
from seed_ado import Seeder

from dhf.ingest.ado import ADO
from dhf.ingest.discovery import discover, discovery_report
from dhf.ingest.fixtures import ingest_fixtures


def semantic(graph: dict) -> dict:
    return {
        "artifacts": [
            {**a, "source": {"system": a["source"]["system"], "revision": a["source"]["revision"]}}
            for a in graph["artifacts"]
        ],
        "links": [{k: v for k, v in e.items() if k != "evidence"} for e in graph["links"]],
    }


def test_seed_empty_project_idempotence_native_parity_and_discovery(tmp_path):
    server = Server(tmp_path / "mock", port=0, empty=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/kestrel-org"
    seed = Seeder(base, "Kestrel", "mock-seed-token", "kestrel-org")
    ado = ADO(base, "Kestrel", "mock-app-token")
    try:
        before = read_state(server.root)
        dry = seed.seed(dry_run=True)
        assert dry["work_items_to_create"] == 126 and read_state(server.root) == before
        result = seed.seed()
        assert result["work_items_created"] == 126
        assert result["runs_created"] == 2 and result["results_created"] == 80
        assert result["prs_created"] == 7
        second = seed.seed()
        print("rerun counts", second)
        assert all(value == 0 for key, value in second.items() if key != "dry_run"), second
        graph = ado.ingest(tmp_path / "clones")
        assert semantic(graph) == semantic(ingest_fixtures())
        report = discover(ado)
        assert report["mapping"] == ado.mapping and report["unknowns"] == []
        assert len(report["inventory"]["area_paths"]) == 6
        print(
            "seed",
            result,
            "rerun",
            second,
            "parity",
            len(graph["artifacts"]),
            len(graph["links"]),
            "discover unknowns",
            len(report["unknowns"]),
        )
    finally:
        seed.close()
        ado.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_seed_writes_require_seed_token_and_confirm_org(ado_server):
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    with pytest.raises(ValueError, match="confirm-org"):
        Seeder(base, "Kestrel", "mock-seed-token", "wrong-org")
    with httpx.Client(base_url=base + "/Kestrel", auth=("", "mock-app-token")) as client:
        for method, path, body in [
            ("POST", "/_apis/wit/workitems/$Requirement", []),
            ("PATCH", "/_apis/wit/workitems/1", []),
            ("POST", "/_apis/test/runs", {}),
            ("POST", "/_apis/test/runs/1/results", []),
            ("PATCH", "/_apis/test/runs/1/results", []),
            ("POST", "/_apis/git/repositories/kestrel-device-sw/pushes", {}),
            (
                "PATCH",
                "/_apis/git/repositories/kestrel-device-sw/pullrequests/1",
                {"status": "completed"},
            ),
        ]:
            assert client.request(method, path, json=body).status_code == 403
    with httpx.Client(base_url=base + "/Kestrel", auth=("", "mock-seed-token")) as client:
        current = client.get("/_apis/wit/workitems/1").json()
        result = client.patch(
            "/_apis/wit/workitems/1",
            json=[
                {"op": "test", "path": "/rev", "value": current["rev"]},
                {
                    "op": "replace",
                    "path": "/fields/System.Title",
                    "value": "Updated synthetic title",
                },
            ],
            headers={"Content-Type": "application/json-patch+json"},
        )
        assert result.status_code == 200 and result.json()["rev"] == current["rev"] + 1


def test_renamed_acceptance_field_requires_human_confirmation(ado_server):
    ado = ADO(f"http://127.0.0.1:{ado_server.server_port}/kestrel-org", "Kestrel", "mock-app-token")
    try:
        items = copy.deepcopy(ado.workitems())
        old = ado.mapping["fields"]["acceptance_criteria"]
        for item in items:
            if old in item["fields"]:
                item["fields"]["Custom.Acceptance"] = item["fields"].pop(old)
        fields = [{"referenceName": "Custom.Acceptance", "name": "Acceptance Criteria"}]
        report = discovery_report(items, fields, [], [], [], ado.mapping)
        assert report["mapping"]["fields"]["acceptance_criteria"] == "Custom.Acceptance"
        assert any(
            u["kind"] == "field" and u["semantic"] == "acceptance_criteria"
            for u in report["unknowns"]
        )
    finally:
        ado.close()
