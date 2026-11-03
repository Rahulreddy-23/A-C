from pathlib import Path

import httpx
import yaml
from mock_ado.state import apply_scenario, git, read_state


def client(server, token: str = "mock-app-token") -> httpx.Client:
    return httpx.Client(
        base_url=f"http://127.0.0.1:{server.server_port}/kestrel-org/Kestrel", auth=("", token)
    )


def test_dataset_links_counts_and_history() -> None:
    data = yaml.safe_load(Path("data/synthetic/evidence.yaml").read_text(encoding="utf-8"))
    ids = [a["id"] for a in data["artifacts"]]
    assert len(ids) == len(set(ids)) == 248
    assert all(e["src"] in ids and e["dst"] in ids for e in data["links"])
    for typ, count in [
        ("user_need", 6),
        ("system_req", 15),
        ("software_req", 35),
        ("hazard", 8),
        ("risk_control", 12),
        ("component", 6),
        ("software_unit", 20),
        ("test_case", 40),
    ]:
        assert sum(a["type"] == typ for a in data["artifacts"]) == count
    assert all(a["attributes"]["synthetic"] for a in data["artifacts"])
    assert not any("/_mock/" in p.read_text(encoding="utf-8") for p in Path("src").rglob("*.py"))
    assert not any("from tools" in p.read_text(encoding="utf-8") for p in Path("src").rglob("*.py"))


def test_workitem_contract_auth_revisions_and_html(ado_server) -> None:
    with client(ado_server) as c:
        result = c.post(
            "/_apis/wit/wiql?api-version=7.1", json={"query": "SELECT [System.Id] FROM WorkItems"}
        )
        assert result.status_code == 200
        data = result.json()
        assert data["queryType"] == "flat"
        ids = [i["id"] for i in data["workItems"]]
        assert len(ids) == 126
        batch = c.post(
            "/_apis/wit/workitemsbatch?api-version=7.1", json={"ids": ids, "$expand": "Relations"}
        ).json()
        assert batch["count"] == len(ids)
        item = batch["value"][0]
        assert item["id"] == ids[0] and item["rev"] >= 1
        assert "System.Title" in item["fields"]
        assert c.get(item["url"]).json()["id"] == item["id"]
        assert c.get(item["url"] + "/revisions").json()["count"] == 1
        assert c.get(item["_links"]["html"]["href"]).status_code == 200
        for v in batch["value"]:
            for relation in v["relations"]:
                assert relation["rel"].startswith(("System.LinkTypes.", "Microsoft.VSTS."))
                assert c.get(relation["url"]).status_code == 200
        assert c.patch(item["url"], json=[]).status_code == 403
        assert (
            c.post("/_apis/git/repositories/kestrel-device-sw/pullrequests", json={}).status_code
            == 403
        )
        assert (
            c.post(f"http://127.0.0.1:{ado_server.server_port}/_mock/reset", json={}).status_code
            == 403
        )
        assert c.post("/_apis/wit/workitemsbatch", json={"ids": ids * 2}).status_code == 400
    with client(ado_server, "wrong") as c:
        assert c.get("/_apis/git/repositories").status_code == 401


def test_tests_git_pr_status_and_scenario_contract(ado_server) -> None:
    with client(ado_server) as c:
        repos = c.get("/_apis/git/repositories?api-version=7.1").json()["value"]
        assert len(repos) == 2 and all(Path(r["remoteUrl"]).is_dir() for r in repos)
        runs = c.get("/_apis/test/runs?api-version=7.1").json()["value"]
        assert [r["id"] for r in runs] == [1, 2]
        for run in runs:
            results = c.get(f"/_apis/test/runs/{run['id']}/results?api-version=7.1").json()
            assert results["count"] == 40
            assert all(
                r["outcome"] in ("Passed", "Failed") and r["testCase"]["id"]
                for r in results["value"]
            )
        prs = c.get(
            "/_apis/git/repositories/kestrel-device-sw/pullrequests?searchCriteria.status=all&api-version=7.1"
        ).json()["value"]
        assert len(prs) == 7
        for pr in prs:
            linked = c.get(
                f"/_apis/git/repositories/kestrel-device-sw/pullrequests/{pr['pullRequestId']}/workitems"
            ).json()
            assert linked["count"] == (
                0
                if pr["pullRequestId"] == 7
                else len(
                    yaml.safe_load(Path("data/synthetic/history.yaml").read_text(encoding="utf-8"))[
                        pr["pullRequestId"] - 1
                    ]["workitems"]
                )
            )
            assert "workitems" not in pr and "statuses" not in pr
            assert (
                c.get(f"/_git/kestrel-device-sw/pullrequest/{pr['pullRequestId']}").status_code
                == 200
            )
        pr = c.post(
            "/_apis/git/repositories/kestrel-dhf-docs/pullrequests",
            json={
                "title": "Draft",
                "sourceRefName": "refs/heads/draft",
                "targetRefName": "refs/heads/main",
            },
        ).json()
        pid = pr["pullRequestId"]
        status = {
            "state": "failed",
            "description": "Review required",
            "context": {"name": "DHF review readiness", "genre": "dhf"},
        }
        assert (
            c.post(
                f"/_apis/git/repositories/kestrel-dhf-docs/pullrequests/{pid}/statuses", json=status
            ).status_code
            == 201
        )
        assert c.get(pr["_links"]["web"]["href"]).status_code == 200
        assert (
            c.get(f"/_apis/git/repositories/kestrel-dhf-docs/pullrequests/{pid}/statuses").json()[
                "value"
            ][0]["state"]
            == "failed"
        )
    state = read_state(ado_server.root)
    native = state["ids"]["SRS-021"]
    old = state["items"][str(native)]["current"]["rev"]
    head = git(["rev-parse", "HEAD"], ado_server.root / "seed-kestrel-device-sw")
    applied = apply_scenario("change_1", ado_server.root)
    assert applied == {"applied": "change_1", "revision": old + 1, "pr": 8, "run": 3}
    assert git(["rev-parse", "HEAD"], ado_server.root / "seed-kestrel-device-sw") != head
    with client(ado_server) as c:
        assert c.get(f"/_apis/wit/workitems/{native}/revisions").json()["count"] == 2
        assert c.get(f"/_apis/wit/workitems/{native}/revisions/1").json()["rev"] == 1
        assert c.get("/_apis/test/runs/3/results").json()["value"][0]["outcome"] == "Failed"
    assert apply_scenario("change_1", ado_server.root) == {"already_applied": "change_1"}
    history = git(["log", "--oneline"], ado_server.root / "seed-kestrel-device-sw")
    assert "AB#" in history and "Adjust occlusion threshold" in history


def test_git_transport_device_guard(ado_server) -> None:
    import subprocess

    work = ado_server.root / "seed-kestrel-device-sw"
    (work / "unauthorized.txt").write_text(
        "product must not publish this", encoding="utf-8", newline="\n"
    )
    git(["add", "."], work)
    git(["commit", "-m", "Guardrail probe"], work)
    try:
        git(["push", "origin", "main"], work, seed=False)
    except subprocess.CalledProcessError as error:
        assert "read-only" in error.stderr
    else:
        raise AssertionError("Product pushed to device repository")


def test_seed_admin_and_reset_contract(ado_server) -> None:
    with client(ado_server, "mock-seed-token") as c:
        base = f"http://127.0.0.1:{ado_server.server_port}"
        assert c.get(base + "/_mock/state").status_code == 200
        assert c.post(base + "/_mock/apply-scenario/change_1").status_code == 200
        # Reset rebuilds every mock repository: well over httpx's 5 s default on Windows git.
        assert c.post(base + "/_mock/reset", timeout=120).status_code == 200
        assert len(c.get(base + "/_mock/state").json()["runs"]) == 2


def test_answer_key_is_exact() -> None:
    from mock_ado.validate import validate_dataset

    assert validate_dataset()["answer_key"] == "exact"


def test_native_expand_revision_and_missing_resource_contract(ado_server) -> None:
    with client(ado_server) as c:
        state = read_state(ado_server.root)
        native = state["ids"]["SRS-030"]
        item = c.get(f"/_apis/wit/workitems/{native}").json()
        assert "relations" not in item
        assert c.get(f"/_apis/wit/workitems/{native}?$expand=relations").json()["relations"]
        assert c.get(f"/_apis/wit/workitems/{native}/revisions/1").json()["rev"] == 1
        batch = c.post("/_apis/wit/workitemsbatch", json={"ids": [native]}).json()["value"][0]
        assert "relations" not in batch
        assert (
            c.get("/_apis/git/repositories/kestrel-device-sw/pullrequests/9999").status_code == 404
        )
        assert c.get("/_apis/test/runs/9999/results").status_code == 404
