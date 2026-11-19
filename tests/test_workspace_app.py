import re
import threading
import time
import zipfile
from collections import Counter
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pytest
import yaml
from test_workspace import PAT, client_for, login, sdd_document

from dhf.generate import generate_document
from dhf.graph import Store
from dhf.ingest.fixtures import ingest_fixtures
from dhf.render.explorer import evidence_findings
from dhf.review import (
    author_section,
    claim_key,
    readiness,
    resolve_suggestion,
    review_validation,
)
from dhf.trace import coverage, rtm
from dhf.workspace import Workspace
from dhf.workspace.insights import dashboard, gap_groups, requirement_trace
from dhf.workspace.server import cell_text, make_workspace_server
from dhf.workspace.sources import ProjectInput, WorkspaceError

API = "/api/projects/design"


def test_review_edits_clear_readiness_like_the_docs_pr(tmp_path: Path) -> None:
    result = generate_document("sstr", ingest_fixtures(), {"release": "1.1"}, out=tmp_path)
    markdown, manifest = result["markdown"], result["manifest"]
    reasons = Counter(b["reason"] for b in readiness(markdown, manifest)["blockers"])
    assert reasons["unresolved_suggestion"] and reasons["human_input_required"]
    keys = list(
        dict.fromkeys(
            claim_key(c)
            for s in manifest["sections"]
            for c in s["claims"]
            if c["kind"] == "suggested"
        )
    )
    rejected = next(c for s in manifest["sections"] for c in s["claims"] if claim_key(c) == keys[0])
    markdown = resolve_suggestion(markdown, keys[0], "rejected", "Reviewer <One>", "Not a fit")
    for key in keys[1:]:
        markdown = resolve_suggestion(markdown, key, "accepted", "Reviewer One", "Matches")
        markdown = resolve_suggestion(markdown, key, "accepted", "Reviewer One", "Re-decided")
    assert rejected["text"] not in markdown
    assert "Reviewer One rationale=Not a fit" in markdown  # angle brackets never reach markers
    assert markdown.count(f"dhf-resolution:{keys[1]} accepted") == markdown.count(
        f"dhf-claim:{keys[1]}"
    )  # one decision per section holding the claim, never stacked
    with pytest.raises(ValueError):
        author_section(markdown, "approvals", "[Human input required]", "R", "", False)
    markdown = author_section(markdown, "approvals", "Recorded in the eQMS.", "R", "", False)
    check = readiness(markdown, manifest)
    assert check["ready"], check["blockers"]
    assert set(check["resolutions"]) == set(keys)
    with pytest.raises(ValueError):
        resolve_suggestion(markdown, keys[0], "accepted", "R", "")
    noted = review_validation(markdown, "0" * 16, "R", "Seen")
    assert review_validation(noted, "0" * 16, "R", "Seen again").count("dhf-validation:") == 1


def test_trace_dashboard_and_gap_groups_agree_with_the_rtm() -> None:
    graph = ingest_fixtures()
    trace = requirement_trace(graph)
    rows, totals = rtm(graph), coverage(graph)
    by_id = {c["id"]: c for c in trace["coverage"]}
    assert len(trace["rows"]) == len(rows)
    assert by_id["verification"]["covered"] == totals["srs_to_test"]["covered"]
    assert by_id["code"]["covered"] == totals["srs_to_code"]["covered"]
    assert all(c["assessable"] for c in trace["coverage"])
    findings, blind, rules = evidence_findings(graph, [])
    groups = gap_groups(findings, blind, [r for group in rules.values() for r in group])
    assert sum(len(g["findings"]) for g in groups) == len(findings)
    assert "other" not in {g["id"] for g in groups}
    view = dashboard(trace, groups, [], graph)
    complete = sum(bool(r["architecture"] and r["verification"]) for r in trace["rows"])
    assert view["traceability"]["complete"] == complete
    assert view["requirements"]["software_req"] == len(rows)


def test_every_finding_rule_has_exactly_one_gap_category() -> None:
    categories = yaml.safe_load(Path("specs/rules/categories.yaml").read_text(encoding="utf-8"))
    assigned = [rule for c in categories["categories"] for rule in c["rules"]]
    rules = {
        rule["id"]
        for name in ("gaps", "document_baseline", "consistency", "risk")
        for rule in yaml.safe_load(Path(f"specs/rules/{name}.yaml").read_text(encoding="utf-8"))[
            "rules"
        ]
    }
    assert sorted(assigned) == sorted(set(assigned)) and set(assigned) == rules


def test_workspace_page_routes_exist_and_load_nothing_external() -> None:
    page = Path("specs/render/workspace.html").read_text(encoding="utf-8")
    assert not re.search(r"""(?:src|href|action)=["']?(?:https?:)?//""", page)
    for route in set(re.findall(r'href="#/([a-z]+)', page)):
        assert route + ":" in page  # each linked area has a page handler
    script = re.search(r"<script>(.*?)</script>", page, re.S)
    assert script and ".innerHTML" not in script[1]  # evidence text is always set as text


def wait_for_draft(client, doc: str) -> dict:
    for _ in range(300):
        state = client.get(f"{API}/documents/{doc}/draft").json()
        if state["job"].get("state") != "running":
            return state
        time.sleep(0.05)
    raise AssertionError("Draft did not finish")


def test_one_draft_runs_at_a_time(tmp_path, monkeypatch) -> None:
    release = threading.Event()

    def slow(self, actor: str, doc: str, provider: str, fresh: bool = False) -> dict:
        release.wait(5)
        return {"updated": False, "version": 0, "stale": []}

    monkeypatch.setattr(Workspace, "draft", slow)
    server, links = make_workspace_server(tmp_path / "design", "design", "owner", [], port=0)
    background = threading.Thread(target=server.serve_forever, daemon=True)
    background.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with client_for(base) as client:
            login(client, links["owner"])
            assert client.post(f"{API}/documents/sdd/draft").status_code == 202
            second = client.post(f"{API}/documents/sad/draft")
            assert second.status_code == 409 and "Another draft" in second.json()["error"]
            release.set()
            assert wait_for_draft(client, "sdd")["job"]["state"] == "done"
            assert client.post(f"{API}/documents/sad/draft").status_code == 202
            assert wait_for_draft(client, "sad")["job"]["state"] == "done"
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        background.join()


def test_browser_projects_drafts_review_approval_and_redline(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "q3Xbm2v0hQyGq3qg1nGZK2m9oXbVh3o0cXwY3bXr1kE=")
    monkeypatch.setenv("DHF_CACHE_ROOT", str(tmp_path / "llm"))
    root = tmp_path / "workspaces" / "design"
    server, links = make_workspace_server(root, "design", "owner", ["engineer"], port=0)
    background = threading.Thread(target=server.serve_forever, daemon=True)
    background.start()
    base = f"http://127.0.0.1:{server.server_port}"
    upload = {"Content-Type": "application/octet-stream"}
    try:
        with client_for(base) as client, client_for(base) as member:
            login(client, links["owner"])
            login(member, links["engineer"])
            bad = client.post("/api/projects", json={"name": "Pump", "release": "Release 2"})
            assert bad.status_code == 400 and bad.json()["error"] == "Check the release field."
            created = client.post("/api/projects", json={"name": "Pump Platform", "release": "2"})
            assert created.status_code == 201 and created.json()["id"] == "pump-platform"
            again = client.post("/api/projects", json={"name": "Pump  platform!", "release": "2"})
            assert again.json()["id"] == "pump-platform-2"
            listed = {p["id"]: p for p in member.get("/api/projects").json()["projects"]}
            assert set(listed) == {"design", "pump-platform", "pump-platform-2"}
            archived = client.post("/api/projects/pump-platform-2/archive", json={"archived": True})
            assert archived.json()["archived"] is True
            assert client.post(f"{API}/documents/sdd/draft").json()["job"]["state"] == "running"
            state = wait_for_draft(client, "sdd")
            assert "release" in state["job"]["error"]  # the first project has no details yet
            details = {"name": "Design", "release": "2.0", "repository_url": "https://x.test/r"}
            assert client.post(f"{API}/details", json=details).status_code == 200
            prd = b"# Product requirements\nThe system records each acknowledged message."
            headers = {**upload, "X-Input-Filename": "PRD.md"}
            assert (
                client.post(
                    f"{API}/documents/sdd/uploads/requirements", content=prd, headers=headers
                )
            ).status_code == 201
            sdd = {**upload, "X-Input-Filename": quote("one.docx")}
            body = sdd_document("Read", PAT)
            assert (
                client.post(f"{API}/documents/sdd/uploads/existing_sdd", content=body, headers=sdd)
            ).status_code == 201
            assert client.post(f"{API}/documents/sdd/draft").status_code == 202
            state = wait_for_draft(client, "sdd")
            assert state["job"]["state"] == "done", state["job"]
            draft = state["draft"]
            assert draft["version"] == 1 and not draft["redline"]
            word = client.get(f"{API}/documents/sdd/files/sdd.docx")
            assert (
                word.status_code == 200
                and "design-sdd-v1.docx" in word.headers["Content-Disposition"]
            )
            assert client.get(f"{API}/documents/sdd/files/../workspace.sqlite").status_code == 404
            review = member.get(f"{API}/review").json()
            for item in review["suggestions"]:
                decision = {"kind": "suggestion", "key": item["key"], "decision": "accepted"}
                answer = member.post(
                    f"{API}/documents/sdd/review", json={**decision, "rationale": "Checked"}
                )
                assert answer.status_code == 200, answer.text
            for item in review["sections"]:
                text = {"kind": "section", "section": item["section"], "text": "Reviewed text."}
                assert (
                    member.post(
                        f"{API}/documents/sdd/review", json={**text, "rationale": "Authored"}
                    ).status_code
                    == 200
                )
            for item in review["rejections"]:
                note = {"kind": "validation", "key": item["key"], "rationale": "Seen"}
                assert member.post(f"{API}/documents/sdd/review", json=note).status_code == 200
            ready = client.get(f"{API}/documents/sdd/draft").json()["draft"]
            assert ready["readiness"]["ready"], ready["readiness"]["blockers"]
            assert client.post(f"{API}/documents/sdd/approval", json={}).status_code == 400
            approval = client.post(f"{API}/documents/sdd/approval", json={"reference": "DCR-7"})
            assert approval.status_code == 201 and approval.json()["approver"] == "owner"
            documents = {d["type"]: d for d in client.get(API).json()["documents"]}
            assert documents["sdd"]["stage"] == "approved"
            assert (root / "sdd" / "baselines" / "sdd-v1.md").is_file()
            other = {**upload, "X-Input-Filename": quote("two.docx")}
            body = sdd_document("Write", "plain text only")
            client.post(f"{API}/documents/sdd/uploads/existing_sdd", content=body, headers=other)
            client.post(f"{API}/documents/sdd/draft")
            updated = wait_for_draft(client, "sdd")
            assert updated["job"]["result"]["updated"] and updated["job"]["result"]["stale"]
            assert updated["draft"]["version"] == 2 and updated["draft"]["redline"]
            xml = zipfile.ZipFile(
                BytesIO(client.get(f"{API}/documents/sdd/files/sdd.docx").content)
            ).read("word/document.xml")
            assert b"<w:ins " in xml
            documents = {d["type"]: d for d in client.get(API).json()["documents"]}
            assert documents["sdd"]["stage"] != "approved"
            views = [client.get(f"{API}/{name}") for name in ("dashboard", "traceability")]
            assert all(v.status_code == 200 for v in views)
            assert views[0].json()["documentation"]["drafted"] == 1
            settings = client.get(f"{API}/settings").json()
            assert settings["ai"]["provider"] == "mock" and settings["encryption_configured"]
            assert PAT not in client.get(f"{API}/review").text
    finally:
        server.shutdown()
        server.server_close()
        background.join()


def test_reject_removes_every_line_of_a_multiline_suggestion() -> None:
    key = "a" * 16
    claim = "**[Suggested — review required]** First line\nsecond line [X@r1](u)"
    body = f"## S\n\n<!-- dhf-claim:{key} -->\n{claim}\n\nKept.\n"
    markdown = f"<!-- section:s -->\n{body}<!-- endsection:s -->\n"
    out = resolve_suggestion(markdown, key, "rejected", "R", "No")
    assert "second line" not in out and "First line" not in out and "Kept." in out


def test_traceability_completeness_skips_levels_inputs_cannot_record() -> None:
    graph = ingest_fixtures()
    for item in graph["artifacts"]:
        item["attributes"]["link_classes"] = ["verifies:test_case"]
    trace = requirement_trace(graph)
    view = dashboard(trace, [], [], graph)
    assert view["traceability"]["levels"] == ["verification"]
    assert view["traceability"]["complete"] == sum(bool(r["verification"]) for r in trace["rows"])
    for item in graph["artifacts"]:
        item["attributes"]["link_classes"] = []
    view = dashboard(requirement_trace(graph), [], [], graph)
    assert view["traceability"]["percent"] is None


def test_project_ids_never_reuse_folders_and_bad_databases_are_skipped(tmp_path) -> None:
    root = tmp_path / "workspaces" / "folder"
    (tmp_path / "workspaces" / "broken").mkdir(parents=True)
    (tmp_path / "workspaces" / "broken" / "workspace.sqlite").write_bytes(b"not a database")
    server, links = make_workspace_server(root, "design", "owner", [], port=0)
    background = threading.Thread(target=server.serve_forever, daemon=True)
    background.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with client_for(base) as client:
            login(client, links["owner"])
            assert client.get("/api/projects").status_code == 200
            made = client.post("/api/projects", json={"name": "Folder", "release": "1"})
            assert made.json()["id"] == "folder-2"
            made = client.post("/api/projects", json={"name": "Broken", "release": "1"})
            assert made.json()["id"] == "broken-2"
    finally:
        server.shutdown()
        server.server_close()
        background.join()


def test_bulk_review_redraft_changes_and_rtm_export(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DHF_CACHE_ROOT", str(tmp_path / "llm"))
    workspace = Workspace(tmp_path / "w", "w", "owner", ["peer"])
    workspace.save_details("owner", ProjectInput(name="W", release="2.0"))
    workspace.upload(
        "owner",
        "sstr",
        "test_evidence",
        "results.csv",
        b"Test Case ID,Outcome,Release\n41,passed,2.0\n42,failed,2.0\n",
    )
    with pytest.raises(WorkspaceError):  # SSTR needs Azure requirements
        workspace.draft("owner", "sstr", "mock")
    graph = ingest_fixtures()
    for item in graph["artifacts"]:
        item["attributes"]["synthetic"] = True
    monkeypatch.setattr(Workspace, "graph", lambda self, actor, doc: graph)
    first = workspace.draft("owner", "sstr", "mock")
    assert first == {"updated": True, "version": 1, "stale": [], "redrafted": False}
    store = Store(tmp_path / "w" / "sstr" / "evidence.sqlite")
    try:
        snapshots = store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0]
    finally:
        store.close()
    assert workspace.draft("owner", "sstr", "mock")["updated"] is False
    store = Store(tmp_path / "w" / "sstr" / "evidence.sqlite")
    try:  # an unchanged update stores no second copy of the evidence
        assert store.db.execute("SELECT count(*) FROM snapshots").fetchone()[0] == snapshots
    finally:
        store.close()
    state = workspace.draft_state("owner", "sstr", with_evidence=True)
    keys = list(
        {claim_key(c) for s in state["sections"] for c in s["claims"] if c["kind"] == "suggested"}
    )
    sourced = next(
        claim_key(c) for s in state["sections"] for c in s["claims"] if c["kind"] == "sourced"
    )
    with pytest.raises(WorkspaceError, match="Only AI suggestions"):
        workspace.review(
            "owner",
            "sstr",
            {"kind": "suggestion", "key": sourced, "decision": "rejected", "rationale": "x"},
        )
    with pytest.raises(WorkspaceError, match="need a person"):
        workspace.review(
            "owner", "sstr", {"kind": "section", "section": "purpose_scope", "text": "x"}
        )
    done = workspace.review(
        "peer",
        "sstr",
        {"kind": "suggestion", "keys": keys, "decision": "accepted", "rationale": "Batch checked"},
    )
    assert set(done["readiness"]["resolutions"]) == set(keys)
    assert {r["reviewer"] for r in done["readiness"]["resolutions"].values()} == {"peer"}
    assert workspace.changes("owner", "sstr") == {"release_changed": False, "sections": []}
    workspace.save_details("owner", ProjectInput(name="W", release="2.1"))
    assert workspace.changes("owner", "sstr")["release_changed"] is True
    redraft = workspace.draft("owner", "sstr", "mock")
    assert redraft["redrafted"] and redraft["version"] == 2
    again = workspace.draft_state("owner", "sstr")
    assert again["version"] == 2 and again["redline"] and again["docx"]["insertions"]
    assert workspace.manifest("sstr")["params"]["release"] == "2.1"
    fresh = workspace.draft("owner", "sstr", "mock", fresh=True)
    assert fresh["redrafted"] and fresh["version"] == 3


def test_rtm_cells_never_run_as_spreadsheet_formulas() -> None:
    assert cell_text("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert cell_text("@SUM(A1)") == "'@SUM(A1)"
    assert cell_text("SRS-001") == "SRS-001"
    assert cell_text(None) == ""


def test_safety_classification_csv_unblocks_sfmea_without_guessing() -> None:
    from dhf.generate import expand_sections, load_spec
    from dhf.workspace.uploads import uploaded_evidence

    azure = ingest_fixtures()
    for item in azure["artifacts"]:
        item["attributes"].pop("safety_class", None)
    spec = load_spec("sfmea")
    with pytest.raises(ValueError, match="Safety class columns"):
        expand_sections(spec, azure)
    components = [a for a in azure["artifacts"] if a["type"] == "component"]
    rows = "Item,Safety class\n" + "".join(f"{c['id']},Class C\n" for c in components[1:])
    rows += f"{components[0]['title'].upper()},a\nnot-an-item,C\n{components[1]['id']},D\n"
    upload = {
        "id": "u1",
        "role": "safety_classification",
        "filename": "classes.csv",
        "digest": "d",
        "uploaded_at": "2026-11-20T00:00:00+00:00",
        "blocks": [{"kind": "para", "text": rows}],
    }
    graph = uploaded_evidence([upload], azure)
    recorded = {a["id"]: a["attributes"].get("safety_class") for a in graph["artifacts"]}
    assert recorded[components[0]["id"]] == "A"  # matched by title, any case
    assert all(recorded[c["id"]] == "C" for c in components[1:])  # an invalid "D" row is ignored
    sourced = next(a for a in graph["artifacts"] if a["id"] == components[0]["id"])
    assert sourced["attributes"]["safety_class_source"] == "classes.csv"
    # A class the evidence already states is never overwritten by the file.
    stated = ingest_fixtures()
    kept = uploaded_evidence([{**upload, "blocks": [{"kind": "para", "text": rows}]}], stated)
    assert {a["id"]: a["attributes"].get("safety_class") for a in kept["artifacts"]}[
        components[0]["id"]
    ] == "B"
    sections = expand_sections(spec, graph)
    units = {s.get("entity") for s in sections if s.get("repeat") == "software_unit"}
    in_b = {
        a["id"]
        for a in graph["artifacts"]
        if a["type"] == "software_unit" and a["attributes"].get("component") == components[0]["id"]
    }
    assert units and not units & in_b
