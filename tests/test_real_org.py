"""Real-organization readiness: read-only guarantee, scoped ingest, rich-text fields."""

from pathlib import Path

import httpx
import pytest
import yaml
from mock_ado.state import read_state

from dhf.ingest.ado import ADO, ReadOnlyViolation, load_scope
from dhf.ingest.discovery import discovery_report
from dhf.ingest.native import normalize_workitem, parse_steps
from dhf.review import DocsReview

REAL = "https://dev.azure.example/example-org"


def offline(ado: ADO, handler) -> list[httpx.Request]:
    """Swap the transport for a recorder, keeping the product's own request guard."""
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return handler(request)

    ado.client.close()
    ado.client = httpx.Client(
        base_url=ado.url,
        transport=httpx.MockTransport(record),
        event_hooks={"request": [ado.guard]},
    )
    return sent


def test_real_orgs_are_read_only_unless_explicitly_opted_out(monkeypatch) -> None:
    assert ADO(REAL, "Project", "placeholder", scope={}).read_only
    assert not ADO("http://127.0.0.1:9/kestrel-org", scope={}).read_only
    monkeypatch.setenv("ADO_READ_ONLY", "1")
    assert ADO("http://127.0.0.1:9/kestrel-org", scope={}).read_only
    monkeypatch.setenv("ADO_READ_ONLY", "0")
    assert not ADO(REAL, "Project", "placeholder", scope={}).read_only


def test_read_only_mode_blocks_every_write_before_the_network() -> None:
    ado = ADO(REAL, "Project", "placeholder", scope={})
    sent = offline(ado, lambda request: httpx.Response(200, json={"workItems": []}))
    with pytest.raises(ReadOnlyViolation):
        ado.request("POST", "/_apis/git/repositories/kestrel-dhf-docs/pullrequests", {})
    with pytest.raises(ReadOnlyViolation):
        ado.client.post("/_apis/git/repositories/kestrel-dhf-docs/pushes", json={})
    with pytest.raises(ValueError, match="forbids"):
        ado.request("PATCH", "/_apis/wit/workitems/1", {})
    review = DocsReview.__new__(DocsReview)
    review.ado = ado
    with pytest.raises(ReadOnlyViolation):
        review.commit("dhf/sstr", "sstr", "", {}, "")
    assert sent == []
    ado.request("POST", "/_apis/wit/wiql", {"query": "SELECT [System.Id] FROM WorkItems"})
    assert [(r.method, r.url.path) for r in sent] == [
        ("POST", "/example-org/Project/_apis/wit/wiql")
    ]


def test_rejected_pat_reports_the_service_reason() -> None:
    ado = ADO(REAL, "Project", "placeholder", scope={})
    reason = "Access%20Denied%3A%20The%20Personal%20Access%20Token%20used%20has%20expired."
    offline(ado, lambda r: httpx.Response(401, headers={"x-tfs-serviceerror": reason}, text="x"))
    with pytest.raises(PermissionError, match="has expired"):
        ado.request("GET", "/_apis/wit/workitems/1")


def test_scope_expands_from_seed_items_along_links_only(ado_server, tmp_path: Path) -> None:
    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["SRS-001"]], "follow": {"depth": 1}, "history": False}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope)
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    # Parent (Hierarchy) and verifying tests (Tested By); Related risk links are not followed.
    assert {a["id"] for a in graph["artifacts"]} == {"SRS-001", "SYS-001", "TC-001", "TC-033"}
    edges = {(e["src"], e["type"], e["dst"]) for e in graph["links"]}
    assert {("SRS-001", "derives_from", "SYS-001"), ("TC-001", "verifies", "SRS-001")} <= edges
    assert ado.report["code evidence not configured"] == 1


def test_scope_limits_and_plan_filtered_results(ado_server, tmp_path: Path) -> None:
    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    wide = ADO(base, "Kestrel", "mock-app-token", scope={"seed_ids": [ids["SRS-001"]]})
    wide.scope["max_items"] = 2
    with pytest.raises(ValueError, match="max_items"):
        wide.workitems()
    wide.close()
    scope = {"seed_ids": [ids["TC-001"]], "follow": {"depth": 0}, "test_plans": ["1"]}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope | {"history": False})
    try:
        graph = ado.ingest(tmp_path / "clones")
        results = [a for a in graph["artifacts"] if a["type"] == "test_result"]
        assert len(results) == 2 and {r["attributes"]["test_case"] for r in results} == {"TC-001"}
        assert ado.report["test results outside scope"] == 78
        assert [i["id"] for i in ado.fetch([ids["SRS-001"], 99999])] == [ids["SRS-001"]]
        assert ado.report["work items unavailable"] == 1
        ado.scope["test_plans"] = ["404"]
        assert ado.test_runs() == []
    finally:
        ado.close()


def test_seed_files_accept_work_item_urls_and_bare_ids(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "https://dev.azure.example/org/Project/_workitems/edit/7\n 12 \nnot an id\n"
    )
    (tmp_path / "scope.yaml").write_text("seed_ids: [3]\nseed_files: [requirements.txt]\n")
    assert load_scope(str(tmp_path / "scope.yaml"))["seed_ids"] == [3, 7, 12]


def test_rich_text_fields_mapped_ids_and_attributes() -> None:
    mapping = {
        "work_item_types": {"Specification": "software_req"},
        "fields": {
            "title": "System.Title",
            "body": "System.Description",
            "state": "System.State",
            "changed_at": "System.ChangedDate",
            "tags": "System.Tags",
        },
        "id_fields": {"software_req": "Custom.SpecID"},
        "attribute_fields": {"feature": "Custom.Feature"},
    }
    fields = {
        "System.WorkItemType": "Specification",
        "System.Title": "Pump list",
        "System.State": "Approved",
        "System.ChangedDate": "2026-10-01T00:00:00Z",
        "Custom.SpecID": "SPEC-KS-17",
        "Custom.Feature": "Fleet view",
        "System.Description": (
            "<div>The application lists pumps.</div><table><tr><td><b>Label</b></td>"
            "<td>Value</td></tr><tr><td>Serial<br>Number</td><td>Pump serial number</td></tr>"
            "</table><ul><li>Sortable</li><li>Searchable</li></ul>"
        ),
    }
    item = {"id": 501, "rev": 3, "fields": fields, "_links": {"html": {"href": "https://x/501"}}}
    artifact = normalize_workitem(item, [item], mapping, "2026-11-03T00:00:00Z")
    assert artifact["id"] == "SPEC-KS-17" and artifact["attributes"]["feature"] == "Fleet view"
    assert artifact["body"] == (
        "The application lists pumps.\nLabel | Value\nSerial Number | Pump serial number\n"
        "- Sortable\n- Searchable"
    )
    mapping["id_fields"] = {}
    mapping["id_formats"] = {"software_req": "SPEC-KS-{id}"}
    assert normalize_workitem(item, [item], mapping, "now")["id"] == "SPEC-KS-501"
    steps = parse_steps(
        '<steps id="0" last="2"><step id="2" type="ActionStep"><parameterizedString '
        'isformatted="true">&lt;DIV&gt;&lt;P&gt;Open the &lt;B&gt;device list&lt;/B&gt;'
        '&lt;/P&gt;&lt;/DIV&gt;</parameterizedString><parameterizedString isformatted="true">'
        "&lt;P&gt;List is shown&lt;/P&gt;</parameterizedString><description/></step></steps>"
    )
    assert steps == [{"action": "Open the device list", "expected": "List is shown"}]


def test_discovery_accepts_reciprocal_links_and_suggests_document_id_fields() -> None:
    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
    items = [
        {
            "id": n,
            "fields": {"System.WorkItemType": "Requirement", "Custom.SpecID": f"SPEC-KS-{n}"},
            "relations": [{"rel": "Microsoft.VSTS.Common.TestedBy-Forward", "url": "x/9"}],
        }
        for n in (1, 2)
    ]
    report = discovery_report(items, [], [], [], [], mapping)
    assert report["inventory"]["id_field_candidates"] == {"Requirement": ["Custom.SpecID"]}
    assert report["inventory"]["custom_fields"] == ["Custom.SpecID"]
    assert not [u for u in report["unknowns"] if u["kind"] == "relation"]
