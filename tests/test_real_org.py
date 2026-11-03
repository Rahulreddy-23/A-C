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


def test_seed_files_accept_every_ado_url_form_and_never_silently_widen(tmp_path: Path) -> None:
    (tmp_path / "seeds.txt").write_text(
        "https://dev.azure.example/org/P/_workitems/edit/101/\n"
        "https://dev.azure.example/org/P/_workitems/edit/102?src=WorkItemMention\n"
        "103 - Pump shall alarm on occlusion\n"
        "https://dev.azure.example/org/P/_apis/wit/workItems/104\n"
        "https://dev.azure.example/org/P/_boards/board?workitem=105\n"
        "# comment\nnot an id\n"
    )
    (tmp_path / "scope.yaml").write_text("seed_files: [seeds.txt]\n")
    scope = load_scope(str(tmp_path / "scope.yaml"))
    assert scope["seed_ids"] == [101, 102, 103, 104, 105] and scope["unparsed_seed_lines"] == 1
    assert ADO(REAL, "P", "x", scope=scope).report["seed lines without a work-item ID"] == 1
    (tmp_path / "empty.txt").write_text("nothing here\n")
    (tmp_path / "broken.yaml").write_text("seed_files: [empty.txt]\nhistory: false\n")
    with pytest.raises(ValueError, match="none could be read"):
        load_scope(str(tmp_path / "broken.yaml"))


def test_run_selection_follows_the_scope_kind(ado_server) -> None:
    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    whole = ADO(base, "Kestrel", "mock-app-token", scope={"max_items": 10000, "seed_ids": []})
    seeded = ADO(base, "Kestrel", "mock-app-token", scope={"seed_ids": [ids["TC-001"]]})
    planned = ADO(base, "Kestrel", "mock-app-token", scope={"seed_ids": [1], "test_plans": ["1"]})
    try:
        assert not whole.seeded and len(whole.test_runs()) == 2
        assert (
            seeded.test_runs() == []
            and seeded.report["test runs not read (no test_plans in scope)"]
        )
        assert len(planned.test_runs()) == 2
    finally:
        for ado in (whole, seeded, planned):
            ado.close()


def test_scoped_ingest_with_a_repository_keeps_only_in_scope_code_links(ado_server, tmp_path):
    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {
        "seed_ids": [ids["SRS-001"]],
        "follow": {"depth": 1},
        "history": False,
        "repository": "kestrel-device-sw",
    }
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope)
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    ids_in = {a["id"] for a in graph["artifacts"]}
    assert all(e["src"] in ids_in and e["dst"] in ids_in for e in graph["links"])
    assert ado.report["code links to items outside scope"] > 0
    assert ("UNIT-infusion_bounds", "SRS-001") in {
        (e["src"], e["dst"]) for e in graph["links"] if e["type"] == "implements"
    }


def test_results_without_cases_and_duplicate_document_ids_do_not_abort(
    ado_server, tmp_path, monkeypatch
):
    from mock_ado.state import write_state

    state = read_state(ado_server.root)
    ids = state["ids"]
    first, second = (state["items"][str(ids[i])]["current"] for i in ("SRS-001", "SRS-002"))
    for item in (first, second):
        item["fields"]["Custom.SpecID"] = "SPEC-KS-17"  # a copied work item keeps its Spec ID
    state["runs"][0]["results"].append(
        {
            "id": 999,
            "testCase": {"name": "Pipeline test"},
            "outcome": "Passed",
            "testRun": {"id": "1"},
        }
    )
    write_state(ado_server.root, state)
    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
    mapping["id_tag_prefix"] = "NONE:"
    mapping["id_fields"] = {"software_req": "Custom.SpecID"}
    (tmp_path / "mapping.yaml").write_text(yaml.safe_dump(mapping))
    monkeypatch.setenv("ADO_MAPPING", str(tmp_path / "mapping.yaml"))
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["SRS-001"], ids["SRS-002"]], "follow": {"depth": 0}}
    ado = ADO(
        base, "Kestrel", "mock-app-token", scope=scope | {"history": False, "test_plans": ["1"]}
    )
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    reqs = sorted(a["id"] for a in graph["artifacts"] if a["type"] == "software_req")
    assert reqs == ["ADO-" + str(ids["SRS-002"]), "SPEC-KS-17"]
    assert ado.report["duplicate document IDs (kept as ADO-<id>)"] == 1
    assert ado.report["test results without a test case"] == 1


def test_discovery_accepts_a_minimal_mapping_profile() -> None:
    mapping = {
        "work_item_types": {"Specification": "software_req"},
        "fields": {"title": "System.Title", "state": "System.State", "changed_at": "X"},
    }
    item = {"id": 1, "fields": {"System.WorkItemType": "Specification", "System.Tags": "A"}}
    report = discovery_report([item], [], [], [], [], mapping)
    assert report["inventory"]["work_item_types"] == {"Specification": 1}


def test_git_channel_refuses_pushes_to_read_only_orgs_and_ignores_credential_helpers(
    tmp_path, monkeypatch
) -> None:
    import subprocess

    from dhf.ingest.ado import git_command, subcommand

    assert subcommand(["-c", "user.name=x", "-c", "user.email=y", "push", "origin"]) == "push"
    subprocess.run(["git", "init", "-q", str(tmp_path / "repo")], check=True)
    remote = "https://dev.azure.example/example-org/P/_git/docs"
    subprocess.run(["git", "-C", str(tmp_path / "repo"), "remote", "add", "origin", remote])
    with pytest.raises(ReadOnlyViolation):
        git_command(["push", "origin", "refs/tags/sstr-v1"], tmp_path / "repo", "placeholder")
    seen = []
    real_run = subprocess.run

    def record(args, **kwargs):
        seen.append((args, kwargs["env"].get("GCM_INTERACTIVE")))
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", record)
    git_command(["status", "--short"], tmp_path / "repo")
    assert seen[-1] == (["git", "-c", "credential.helper=", "status", "--short"], "never")


def test_docs_review_refuses_baselines_in_read_only_mode() -> None:
    ado = ADO(REAL, "Project", "placeholder", scope={})
    sent = offline(ado, lambda request: httpx.Response(200, json={"status": "completed"}))
    review = DocsReview.__new__(DocsReview)
    review.ado = ado
    with pytest.raises(ReadOnlyViolation):
        review.create_baseline("sstr", 7)
    with pytest.raises(ReadOnlyViolation):
        review.push("refs/tags/sstr-v1")
    assert sent == []


def test_rich_text_edge_cases_and_literal_angle_brackets_in_steps() -> None:
    from dhf.ingest.native import html_text

    assert html_text("<table><tr><td>Serial<td>Pump serial<tr><td>Model<td>K1</table>") == (
        "Serial | Pump serial\nModel | K1"
    )
    nested = (
        "<table><tr><td>Outer<table><tr><td>Inner</td></tr></table>after</td>"
        "<td>B</td></tr></table>"
    )
    assert html_text(nested) == "Outer Inner after | B"
    assert html_text("<ul><li><p>Alarm sounds</p></li><li><div>Light</div></li></ul>") == (
        "- Alarm sounds\n- Light"
    )
    steps = parse_steps(
        '<steps id="0" last="2"><step id="2" type="ActionStep"><parameterizedString '
        'isformatted="true">&lt;P&gt;Press &amp;lt;Enter&amp;gt; and type &amp;lt;user&amp;gt;'
        '&lt;/P&gt;</parameterizedString><parameterizedString isformatted="true">'
        "Value x&amp;lt;limit &amp;amp; shown</parameterizedString></step></steps>"
    )
    assert steps == [
        {"action": "Press <Enter> and type <user>", "expected": "Value x<limit & shown"}
    ]


def test_synthetic_tag_counts_only_when_the_mapping_names_one() -> None:
    from dhf.ingest.native import synthetic_marker

    assert not synthetic_marker("", ["Synthetic"], {"fields": {}})
    assert synthetic_marker("", ["Synthetic"], {"tags": {"synthetic": "Synthetic"}})


def test_real_project_ids_are_recognised_and_invented_ones_rejected() -> None:
    from dhf.generate.validator import validate_claims
    from dhf.models.values import ID_PATTERN

    text = "PREQ-KS-1670 maps to SI-Fleet-Service, UNIT-Fleet.Ks.Fleet.Core, SPEC-KS-17, ADO-4."
    assert ID_PATTERN.findall(text) == [
        "PREQ-KS-1670",
        "SI-Fleet-Service",
        "UNIT-Fleet.Ks.Fleet.Core",
        "SPEC-KS-17",
        "ADO-4",
    ]
    assert not ID_PATTERN.findall("IEC 62304, UTF-8 and SHA-256")
    pack = {"facts": {}, "evidence": [{"id": "SPEC-KS-17", "body": "", "attributes": {}}]}
    claims = [
        {"text": "SPEC-KS-17 is verified.", "kind": "sourced", "citations": ["SPEC-KS-17"]},
        {"text": "SI-Ghost-Service also implements it.", "kind": "sourced", "citations": []},
    ]
    result = validate_claims({"claims": claims}, pack, ["sourced", "inferred"], 5)
    assert [c["text"] for c in result["claims"]] == ["SPEC-KS-17 is verified."]
    assert result["validation"]["rejected"] == [
        {"claim_index": 1, "reason": "unknown_ids", "ids": ["SI-Ghost-Service"]}
    ]


def test_outdated_verification_ignores_results_without_a_date() -> None:
    from dhf.ingest.fixtures import ingest_fixtures
    from dhf.trace import gaps

    graph = ingest_fixtures()
    for artifact in graph["artifacts"]:
        if artifact["type"] == "test_result":
            artifact["attributes"]["completed_at"] = ""
    assert not [f for f in gaps(graph) if f["rule"] == "G11"]


def test_discovery_works_with_a_pat_that_cannot_read_code() -> None:
    from dhf.ingest.discovery import discover

    ado = ADO(REAL, "Project", "placeholder", scope={"seed_ids": [1], "test_plans": []})

    def answer(request: httpx.Request) -> httpx.Response:
        if "/_apis/git/" in request.url.path:
            return httpx.Response(401, headers={"x-tfs-serviceerror": "TF400813"}, text="x")
        if request.url.path.endswith("/workitemsbatch"):
            item = {"id": 1, "rev": 1, "fields": {"System.WorkItemType": "Requirement"}}
            return httpx.Response(200, json={"value": [item]})
        return httpx.Response(200, json={"value": []})

    offline(ado, answer)
    report = discover(ado)
    assert report["inventory"]["repositories"].startswith("not readable with this PAT")
    assert report["inventory"]["work_item_types"] == {"Requirement": 1}


def test_associated_bugs_outside_the_scope_are_read_not_reported_missing(ado_server, tmp_path):
    from mock_ado.state import write_state

    from dhf.trace import gaps

    state = read_state(ado_server.root)
    ids = state["ids"]
    for result in state["runs"][0]["results"]:
        if result["testCase"]["id"] == str(ids["TC-001"]):
            result["outcome"] = "Failed"
            result["associatedBugs"] = [{"id": ids["BUG-02"]}]
    write_state(ado_server.root, state)
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["TC-001"], ids["BUG-01"]], "follow": {"depth": 0}}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope | {"test_plans": ["1"]})
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    assert "BUG-02" in {a["id"] for a in graph["artifacts"]}
    assert ado.report["associated bugs read outside scope"] == 1
    failed = [a["id"] for a in graph["artifacts"] if a["attributes"].get("outcome") == "Failed"]
    assert failed and not [
        f for f in gaps(graph) if f["rule"] == "G05" and f["artifact_id"] in failed
    ]


def test_mappings_cannot_overwrite_reserved_attributes() -> None:
    mapping = {
        "work_item_types": {"Specification": "software_req"},
        "fields": {
            "title": "System.Title",
            "state": "System.State",
            "changed_at": "System.ChangedDate",
        },
        "attribute_fields": {"synthetic": "Custom.SyntheticData"},
    }
    fields = {
        "System.WorkItemType": "Specification",
        "System.Title": "T",
        "System.State": "Active",
        "System.ChangedDate": "2026-10-01T00:00:00Z",
        "Custom.SyntheticData": "No",
    }
    item = {"id": 5, "rev": 1, "fields": fields, "_links": {"html": {"href": "https://x/5"}}}
    with pytest.raises(ValueError, match="reserved attribute 'synthetic'"):
        normalize_workitem(item, [item], mapping, "now")


def test_scope_follows_the_mappings_trace_links_by_default(tmp_path, monkeypatch) -> None:
    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
    mapping["relations"]["derives_from"] = "System.LinkTypes.Dependency-Reverse"
    (tmp_path / "mapping.yaml").write_text(yaml.safe_dump(mapping))
    monkeypatch.setenv("ADO_MAPPING", str(tmp_path / "mapping.yaml"))
    follow = ADO(REAL, "P", "x", scope={}).follow_default()
    assert {"System.LinkTypes.Dependency-Forward", "System.LinkTypes.Dependency-Reverse"} <= follow
    assert "System.LinkTypes.Related" not in follow


def test_sources_the_scope_never_read_make_rules_not_assessable(ado_server, tmp_path) -> None:
    from dhf.trace import gaps, unassessable_rules
    from dhf.trace.reports import gap_rules

    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["SRS-001"]], "follow": {"depth": 1}, "history": False}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope)
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    blind = unassessable_rules(graph, gap_rules())
    assert "G02" in blind and not [f for f in gaps(graph) if f["rule"] == "G02"]
    assert "G01" not in blind and "G09" not in blind  # Tested By and Parent links were read


def test_scope_release_labels_runs_whose_names_carry_none(ado_server, tmp_path) -> None:
    from mock_ado.state import write_state

    from dhf.trace import results_summary

    state = read_state(ado_server.root)
    state["runs"][0]["name"] = "Bench Rig (Manual)"
    write_state(ado_server.root, state)
    ids = state["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["TC-001"]], "follow": {"depth": 0}, "test_plans": ["1"]}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope | {"history": False, "release": "1.0"})
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    runs = {
        a["title"]: a["attributes"]["release"]
        for a in graph["artifacts"]
        if a["type"] == "test_run"
    }
    assert runs["Bench Rig (Manual)"] == "1.0"
    assert results_summary(graph, "1.0")["total"] == 1


def test_runs_without_in_scope_results_are_not_evidence(ado_server, tmp_path) -> None:
    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["TC-001"]], "follow": {"depth": 0}, "test_plans": ["1"]}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope | {"history": False})
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    runs = [a for a in graph["artifacts"] if a["type"] == "test_run"]
    results = [a for a in graph["artifacts"] if a["type"] == "test_result"]
    assert {r["attributes"]["run"] for r in results} == {r["id"] for r in runs}


def test_scope_release_must_be_quoted_text(tmp_path: Path) -> None:
    scope_file = tmp_path / "scope.yaml"
    scope_file.write_text("seed_ids: [1]\nrelease: 1.10\n")  # YAML reads the number 1.1
    with pytest.raises(ValueError, match='quoted text, e.g. release: "1.1"'):
        load_scope(str(scope_file))
    scope_file.write_text('seed_ids: [1]\nrelease: "1.10"\n')
    assert load_scope(str(scope_file))["release"] == "1.10"
    scope_file.write_text("seed_ids: [1]\nrelease:\n")  # blank: no release, never "None"
    assert load_scope(str(scope_file))["release"] is None


def test_empty_relations_follow_no_links_and_every_link_type_has_two_ends(ado_server, tmp_path):
    from dhf.ingest.ado import reciprocal

    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    counts = {}
    for name, follow in (("default", {"depth": 1}), ("none", {"depth": 1, "relations": []})):
        ado = ADO(base, "Kestrel", "mock-app-token", scope={"seed_ids": [ids["SRS-001"]]})
        try:
            counts[name] = len(ado.expand({ids["SRS-001"]}, follow, 100))
        finally:
            ado.close()
    assert counts["none"] == 1 < counts["default"]
    assert reciprocal("Microsoft.VSTS.Common.Affects-Reverse") == (
        "Microsoft.VSTS.Common.Affects-Forward"
    )
    assert reciprocal("System.LinkTypes.Related") == "System.LinkTypes.Related"


def test_mapped_work_item_links_never_make_code_rules_assessable(
    ado_server, tmp_path, monkeypatch
) -> None:
    from dhf.trace import gaps, unassessable_rules
    from dhf.trace.reports import gap_rules

    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
    mapping["relations"]["implements"] = "System.LinkTypes.Dependency-Forward"
    (tmp_path / "mapping.yaml").write_text(yaml.safe_dump(mapping))
    monkeypatch.setenv("ADO_MAPPING", str(tmp_path / "mapping.yaml"))
    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    scope = {"seed_ids": [ids["SRS-001"]], "follow": {"depth": 1}, "history": False}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope | {"repository": ""})
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    assert "G02" in unassessable_rules(graph, gap_rules())  # no repository: no code changes
    assert not [f for f in gaps(graph) if f["rule"] == "G02"]


def test_scope_release_labels_only_its_test_plans_and_whole_reads_keep_empty_runs(
    ado_server, tmp_path
) -> None:
    from mock_ado.state import write_state

    state = read_state(ado_server.root)
    state["runs"][0]["name"] = "Bench Rig (Manual)"
    state["runs"].append(
        {
            "id": 99,
            "name": "Release 1.1 aborted run",
            "state": "Aborted",
            "plan": {"id": "1", "name": "Kestrel system verification"},
            "completedDate": "2026-10-01T00:00:00Z",
            "buildConfiguration": {"platform": "Bench"},
            "comment": "Aborted before any result",
            "results": [],
        }
    )
    write_state(ado_server.root, state)
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    ado = ADO(base, "Kestrel", "mock-app-token", scope={"release": "9.9", "history": False})
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    runs = {
        a["id"]: a["attributes"]["release"] for a in graph["artifacts"] if a["type"] == "test_run"
    }
    assert "9.9" not in runs.values()  # no test_plans: the scope release labels nothing
    assert ado.report["scope release ignored (no test_plans)"] == 1
    assert runs["RUN-99"] == "1.1"  # a whole-project read keeps a run without results


def test_seeded_scopes_only_assess_what_they_follow_and_read(ado_server, tmp_path) -> None:
    from dhf.trace import gaps, unassessable_rules
    from dhf.trace.reports import gap_rules

    ids = read_state(ado_server.root)["ids"]
    base = f"http://127.0.0.1:{ado_server.server_port}/kestrel-org"
    # Related links (risk control → requirement) are never followed by default, and no
    # test plans means no results: those rules must read "not assessable", not zero or gaps.
    scope = {"seed_ids": [ids["RC-01"]], "follow": {"depth": 1}, "history": False}
    ado = ADO(base, "Kestrel", "mock-app-token", scope=scope | {"repository": ""})
    try:
        graph = ado.ingest(tmp_path / "clones")
    finally:
        ado.close()
    blind = unassessable_rules(graph, gap_rules())
    assert {"G05", "G06", "G11"} <= set(blind)
    assert not [f for f in gaps(graph) if f["rule"] == "G06"]
