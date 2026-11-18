import base64
import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import pytest
import respx
from cryptography.fernet import Fernet
from docx import Document

from dhf.generate import generate_document, prepare_ai, section_pack
from dhf.graph import Store
from dhf.trace import results_summary
from dhf.workspace import Workspace
from dhf.workspace.server import make_workspace_server
from dhf.workspace.sources import ConnectionInput, WorkspaceError

AZURE = "https://dev.azure.com/tenant"
PROJECT = "Engineering"
WIT = f"{AZURE}/{PROJECT}/_apis/wit"
TEST = f"{AZURE}/{PROJECT}/_apis/test"
API = "/api/projects/design"
PAT = "t9A" * 16 + "WXYZ"
NEW_PAT = "f8B" * 16 + "ABCD"
QUERY = "6ce954b1-ce1f-45d1-b94d-e6bf2464ba2c"


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    key = Fernet.generate_key()
    monkeypatch.setenv("APP_ENCRYPTION_KEY", key.decode())
    return key


@pytest.fixture
def server(tmp_path: Path, key: bytes) -> Iterator[tuple[str, dict, Path]]:
    root = tmp_path / "project"
    server, links = make_workspace_server(root, "design", "owner", ["engineer"], port=0)
    background = threading.Thread(target=server.serve_forever, daemon=True)
    background.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", links, root
    finally:
        server.shutdown()
        server.server_close()
        background.join()


def connection_input(**changes: object) -> dict:
    return {
        "org_url": AZURE,
        "project_name": PROJECT,
        "query_type": "work_item_ids",
        "query_value": "1, 2",
        "pat": PAT,
        **changes,
    }


def login(client: httpx.Client, url: str) -> None:
    grant = urlsplit(url).fragment.split("=", 1)[1]
    response = client.post("/api/session", headers={"Authorization": "Bearer " + grant})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["Set-Cookie"]
    assert "SameSite=Strict" in response.headers["Set-Cookie"]


def client_for(base: str) -> httpx.Client:
    return httpx.Client(base_url=base, headers={"Origin": base}, trust_env=False)


def item(wid: int, kind: str, body: str = "", project: str = PROJECT) -> dict:
    return {
        "id": wid,
        "rev": 2,
        "fields": {
            "System.TeamProject": project,
            "System.Title": "Recorded " + kind,
            "System.WorkItemType": kind,
            "System.ChangedDate": "2026-10-21T15:00:00Z",
            "System.State": "Active",
            "System.Description": body,
        },
    }


def test_pat_encrypted_and_audited_without_value(server, key, caplog, capsys) -> None:
    base, links, root = server
    endpoint = API + "/azure-connections"
    with client_for(base) as stranger, client_for(base) as owner, client_for(base) as member:
        assert stranger.post(endpoint, json=connection_input()).status_code == 401
        login(owner, links["owner"])
        login(member, links["engineer"])
        assert (
            owner.post(
                endpoint, json=connection_input(), headers={"Origin": "http://elsewhere"}
            ).status_code
            == 403
        )
        assert owner.get("/api/projects/other/documents/sad/inputs").status_code == 404
        saved = owner.post(endpoint, json=connection_input())
        assert saved.status_code == 200, saved.text
        cid = saved.json()["id"]
        assert saved.json()["pat_mask"] == "••••••••WXYZ"
        assert saved.json()["pat_saved_at"]
        assert {"pat", "pat_last4", "encrypted_pat"}.isdisjoint(saved.json())
        with closing(sqlite3.connect(root / "workspace.sqlite")) as db:
            encrypted = db.execute("SELECT encrypted_pat FROM azure_connections").fetchone()[0]
        assert isinstance(encrypted, bytes) and Fernet(key).decrypt(encrypted).decode() == PAT
        assert PAT.encode() not in (root / "workspace.sqlite").read_bytes()
        rotated = member.post(endpoint, json=connection_input(pat=NEW_PAT))
        assert rotated.status_code == 200 and rotated.json()["pat_mask"].endswith("ABCD")
        removed = owner.delete(f"{endpoint}/{cid}/pat")
        assert removed.status_code == 200 and removed.json()["pat_mask"] is None
        state = owner.get(f"{API}/documents/sad/inputs")
        assert [(e["action"], e["actor"]) for e in state.json()["audit"]] == [
            ("pat_removed", "owner"),
            ("pat_replaced", "engineer"),
            ("pat_saved", "owner"),
        ]
        with closing(sqlite3.connect(root / "workspace.sqlite")) as db:
            assert db.execute(
                "SELECT encrypted_pat,pat_last4 FROM azure_connections"
            ).fetchone() == (
                None,
                None,
            )
        output = capsys.readouterr()
        text = "".join(r.text for r in (saved, rotated, removed, state)) + caplog.text + output.err
        assert PAT not in text and NEW_PAT not in text and encrypted.decode() not in text


def test_authorization_and_connection_expiry_fail_without_network(tmp_path, key) -> None:
    workspace = Workspace(tmp_path / "project", "design", "owner", [])
    expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    change = ConnectionInput.model_validate(connection_input(pat_expiry=expired))
    with pytest.raises(WorkspaceError) as error:
        workspace.save_connection("guest", change)
    assert error.value.status == 403
    saved = workspace.save_connection("owner", change)
    assert saved["pat_expiry"] == expired
    with pytest.raises(WorkspaceError, match="expired") as error:
        workspace.fetch_or_test("owner", saved["id"], "sad", fetch=False)
    assert error.value.status == 401 and error.value.action == "Update PAT"
    with pytest.raises(WorkspaceError, match="organization URL"):
        workspace.save_connection(
            "owner",
            ConnectionInput.model_validate(
                connection_input(org_url="https://dev.azure.com@somewhere.example/tenant")
            ),
        )


@pytest.mark.parametrize("status", [401, 403])
def test_ado_auth_error_is_sanitized(server, status, caplog) -> None:
    base, links, _ = server
    with respx.mock(assert_all_called=True) as wire, client_for(base) as client:
        wire.route(host="127.0.0.1").pass_through()
        check = wire.get(WIT + "/workitemtypes").respond(
            status,
            headers={"x-tfs-serviceerror": "Private Azure response " + PAT},
            json={"message": PAT},
        )
        login(client, links["owner"])
        cid = client.post(API + "/azure-connections", json=connection_input()).json()["id"]
        response = client.post(f"{API}/azure-connections/{cid}/test", json={"document_type": "sad"})
        assert response.status_code == status
        assert response.json()["action"] == "Update PAT"
        assert PAT not in response.text + caplog.text
        assert check.calls.last.request.headers["Authorization"] == (
            "Basic " + base64.b64encode(f":{PAT}".encode()).decode()
        )


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("work_item_ids", "1, 2"),
        ("saved_query", QUERY),
        ("wiql", "SELECT [System.Id] FROM WorkItems WHERE [System.Id] <= 2"),
        ("area_path", "Engineering\\Device"),
    ],
)
def test_selector_fetches_and_persists_scoped_requirements(server, kind, value) -> None:
    base, links, root = server
    with respx.mock(assert_all_called=True) as wire, client_for(base) as client:
        wire.route(host="127.0.0.1").pass_through()
        wire.get(WIT + "/workitemtypes").respond(json={"value": []})
        if kind == "saved_query":
            wire.get(WIT + "/wiql/" + QUERY).respond(
                json={"workItemRelations": [{"target": {"id": 1}}, {"target": {"id": 2}}]}
            )
        elif kind != "work_item_ids":
            search = wire.post(WIT + "/wiql").respond(json={"workItems": [{"id": 1}, {"id": 2}]})
        batch = wire.post(WIT + "/workitemsbatch").respond(
            json={
                "value": [
                    item(1, "User Story", f"<p>Requirement body {PAT}</p>"),
                    item(2, "Requirement", project="Other project"),
                ]
            }
        )
        login(client, links["owner"])
        saved = client.post(
            API + "/azure-connections",
            json=connection_input(
                query_type=kind,
                query_value=value,
            ),
        )
        assert saved.status_code == 200, saved.text
        cid = saved.json()["id"]
        test = client.post(f"{API}/azure-connections/{cid}/test", json={"document_type": "sad"})
        assert test.json() == {"verified_access": ["Work Items (Read)"], "pat_expiry": None}
        fetch = client.post(f"{API}/azure-connections/{cid}/fetch", json={"document_type": "sad"})
        assert fetch.status_code == 201, fetch.text
        assert fetch.json()["requirements"] == 1
        assert json.loads(batch.calls.last.request.content)["ids"] == [1, 2]
        if kind == "area_path":
            assert (
                "UNDER 'Engineering\\Device'"
                in json.loads(search.calls.last.request.content)["query"]
            )
        state = client.get(f"{API}/documents/sad/inputs").json()
        assert state["snapshot"]["id"] == fetch.json()["id"]
        preview = client.get(f"{API}/documents/sad/evidence")
        assert preview.status_code == 200 and "Kestrel" not in preview.text
        assert client.post(f"{API}/documents/sad/snapshot").status_code == 201
        store = Store(root / "sad" / "evidence.sqlite")
        try:
            graph = store.graph()
        finally:
            store.close()
        record = graph["artifacts"][0]
        assert record["source"]["revision"] == "2"
        assert record["id"] == "ADO-1" and record["body"] == "Requirement body [REDACTED]"
        assert record["attributes"]["synthetic"] is False
        with closing(sqlite3.connect(root / "workspace.sqlite")) as db:
            graph_json = db.execute("SELECT graph FROM requirements_snapshots").fetchone()[0]
        assert PAT not in graph_json


def test_document_override_isolated_and_test_management_checked(server) -> None:
    base, links, _ = server
    with respx.mock() as wire, client_for(base) as client:
        wire.route(host="127.0.0.1").pass_through()
        wire.get(WIT + "/workitemtypes").respond(json={"value": []})
        wire.get(TEST + "/runs").respond(status_code=403)
        login(client, links["owner"])
        default = client.post(API + "/azure-connections", json=connection_input()).json()
        override = client.post(
            API + "/azure-connections",
            json=connection_input(
                document_type="sstr",
                pat=NEW_PAT,
                test_run_ids=[73],
            ),
        ).json()
        assert override["id"] != default["id"]
        assert (
            client.post(f"{API}/documents/sstr/source", json={"mode": "override"}).status_code
            == 200
        )
        state = client.get(f"{API}/documents/sstr/inputs").json()
        assert state["source"] == "override" and len(state["connections"]) == 2
        other = client.get(f"{API}/documents/sad/inputs").json()
        assert other["source"] == "default" and len(other["connections"]) == 1
        route = f"{API}/azure-connections/{override['id']}/test"
        assert client.post(route, json={"document_type": "sad"}).status_code == 404
        assert client.post(route, json={"document_type": "sstr"}).status_code == 403


def test_sstr_fetch_adds_selected_plan_and_run_results(server) -> None:
    base, links, root = server
    with respx.mock() as wire, client_for(base) as client:
        wire.route(host="127.0.0.1").pass_through()
        wire.get(WIT + "/workitemtypes").respond(json={"value": []})
        run = {"id": 73, "name": "Release 2.0", "completedDate": "2026-10-21T18:00:00Z"}
        wire.get(TEST + "/runs", params={"$top": "1"}).respond(json={"value": []})
        wire.get(TEST + "/runs", params={"planId": "5"}).respond(json={"value": [run]})
        wire.get(TEST + "/runs/73").respond(json=run)
        wire.get(TEST + "/runs/73/results").respond(
            json={
                "value": [
                    {
                        "id": 230,
                        "testCase": {"id": "4"},
                        "outcome": "Passed",
                        "completedDate": "2026-10-21T18:00:00Z",
                    }
                ]
            }
        )
        wire.post(WIT + "/workitemsbatch").mock(
            side_effect=lambda request: httpx.Response(
                200,
                json={
                    "value": [
                        item(wid, {1: "Requirement", 4: "Test Case"}[wid])
                        for wid in json.loads(request.content)["ids"]
                    ]
                },
            )
        )
        login(client, links["owner"])
        saved = client.post(
            API + "/azure-connections",
            json=connection_input(
                query_value="1",
                test_plan_ids=[5],
                test_run_ids=[73],
            ),
        )
        assert saved.status_code == 200, saved.text
        cid = saved.json()["id"]
        response = client.post(
            f"{API}/azure-connections/{cid}/fetch", json={"document_type": "sstr"}
        )
        assert response.status_code == 201, response.text
        assert response.json()["artifact_counts"] == {
            "software_req": 1,
            "test_case": 1,
            "test_result": 1,
            "test_run": 1,
        }
        saved = client.post(f"{API}/documents/sstr/snapshot")
        assert saved.status_code == 201, saved.text
    store = Store(root / "sstr" / "evidence.sqlite")
    try:
        assert results_summary(store.graph(), "2.0")["passed"] == 1
    finally:
        store.close()


def sdd_document(unit: str, secret: str) -> bytes:
    document = Document()
    document.add_heading("Service", level=1)
    document.add_heading(unit, level=2)
    document.add_heading("Software Unit Description", level=3)
    paragraph = document.add_paragraph("Token in original input ")
    paragraph.add_run(secret[:25])
    paragraph.add_run(secret[25:]).bold = True
    document.add_heading("Processing Logic", level=3)
    document.add_paragraph("Process the message.")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def test_multiple_sdds_are_redacted_before_evidence_and_ai(server, tmp_path: Path) -> None:
    base, links, root = server
    other_secret = "s" * 76 + "AZDO" + "wxyz"
    with client_for(base) as client:
        login(client, links["owner"])
        assert client.post(API + "/azure-connections", json=connection_input()).status_code == 200
        assert client.post(f"{API}/documents/sdd/snapshot").status_code == 422
        assert (
            client.post(
                f"{API}/documents/sdd/uploads/requirements",
                content=b"# Product requirements\nThe system records each acknowledged message.",
                headers={"Content-Type": "application/octet-stream", "X-Input-Filename": "PRD.md"},
            ).status_code
            == 201
        )
        for name, unit, secret in (("one.docx", "Read", PAT), ("two.docx", "Write", other_secret)):
            response = client.post(
                f"{API}/documents/sdd/uploads/existing_sdd",
                content=sdd_document(unit, secret),
                headers={
                    "Content-Type": "application/octet-stream",
                    "X-Input-Filename": quote(name),
                },
            )
            assert response.status_code == 201, response.text
            assert response.json()["redactions"] >= 1
        assert client.post(f"{API}/documents/sdd/snapshot").status_code == 201
    store = Store(root / "sdd" / "evidence.sqlite")
    try:
        graph = store.graph()
    finally:
        store.close()
    units = {a["title"]: a for a in graph["artifacts"] if a["type"] == "software_unit"}
    assert set(units) == {"Read", "Write"}
    assert all("[REDACTED]" in a["body"] for a in units.values())
    section = {
        "mode": "ai",
        "query": "runtime_view",
        "prompt": "design.conventions@2",
        "allowed_kinds": ["sourced"],
        "synthesis": True,
    }
    evidence = section_pack(section, graph, {"release": "2.0"})
    assert {"one.docx", "two.docx"} <= {a["attributes"]["input_file"] for a in evidence["evidence"]}
    _, chunks, _ = prepare_ai(section, evidence)
    drafts = generate_document("sdd", graph, {"release": "2.0"}, out=tmp_path / "draft")
    for secret in (PAT, other_secret):
        assert secret not in json.dumps([graph, chunks, drafts])
        assert secret.encode() not in (root / "workspace.sqlite").read_bytes()


def test_csv_results_can_generate_sstr(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "project", "design", "owner", [])
    upload = workspace.upload(
        "owner",
        "sstr",
        "test_evidence",
        "results.csv",
        b"Test Case ID,Outcome,Release\n41,passed,2.0\n42,failed,2.0\n",
    )
    assert upload["filename"] == "results.csv"
    graph = workspace.graph("owner", "sstr")
    assert results_summary(graph, "2.0") == {
        "release": "2.0",
        "total": 2,
        "passed": 1,
        "failed": 1,
        "blocked": 0,
        "not_run": 0,
    }
    draft = generate_document("sstr", graph, {"release": "2.0"}, out=tmp_path / "draft")
    assert "Kestrel" not in draft["markdown"]
