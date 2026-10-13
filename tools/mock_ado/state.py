"""Synthetic test tooling, kept separate from the product."""

import base64
import copy
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from dhf.ingest.native import fixture_item

ROOT = Path("out/mock_ado")
DATA = Path("data/synthetic")
WORK_TYPES = {
    "user_need": ("Requirement", "UN"),
    "system_req": ("Requirement", "SYS"),
    "software_req": ("Requirement", "SRS"),
    "risk_control": ("Requirement", "RISK-CONTROL"),
    "hazard": ("Risk", ""),
    "defect": ("Bug", ""),
    "test_case": ("Test Case", ""),
    "review": ("Review", ""),
    "action_item": ("Task", ""),
}


def git(args: list[str], cwd: Path, seed: bool = True, strip: bool = True) -> str:
    env = dict(os.environ, DHF_GIT_ROLE="seed" if seed else "app")
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip() if strip else result.stdout


def write_state(root: Path, state: dict) -> None:
    temp = root / "state.tmp"
    temp.write_text(json.dumps(state))
    temp.replace(root / "state.json")


def read_state(root: Path) -> dict:
    return json.loads((root / "state.json").read_text())


def payload(artifact: dict) -> str:
    return artifact["body"] + '\nDHF-META:{"synthetic": true}'


def init(root: Path = ROOT, empty: bool = False) -> dict:
    if (root / "state.json").exists():
        return read_state(root)
    root.mkdir(parents=True, exist_ok=True)
    dataset = yaml.safe_load((DATA / "evidence.yaml").read_text())
    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
    artifacts = dataset["artifacts"]
    eligible = [] if empty else [a for a in artifacts if a["type"] in WORK_TYPES]
    ids = {a["id"]: i for i, a in enumerate(eligible, 1)}
    items = {}
    for a in eligible:
        attrs = a["attributes"]
        item = fixture_item(a, ids[a["id"]], mapping)
        item.pop("_links")
        item["fields"]["System.Description"] = payload(a)
        for edge in dataset["links"]:
            if edge["src"] == a["id"] and edge["dst"] in ids:
                item["relations"].append(
                    {
                        "rel": mapping["relations"].get(edge["type"], "System.LinkTypes.Related"),
                        "url": f"_apis/wit/workitems/{ids[edge['dst']]}",
                        "attributes": {"name": "Related"},
                    }
                )
        history = []
        for revision in attrs.get(
            "requirement_history",
            [{"revision": item["rev"], "changed_at": item["fields"]["System.ChangedDate"]}],
        ):
            prior = copy.deepcopy(item)
            prior["rev"] = revision["revision"]
            prior["fields"]["System.ChangedDate"] = revision["changed_at"]
            history.append(prior)
        items[str(item["id"])] = {"current": item, "history": history}
    repo_root = root / "git"
    repo_root.mkdir(exist_ok=True)
    repos = []
    for name in ("kestrel-device-sw", "kestrel-dhf-docs"):
        bare = (repo_root / f"{name}.git").resolve()
        git(["init", "--bare", "--initial-branch=main", str(bare)], root)
        work = root / ("seed-" + name)
        work.mkdir()
        git(["init", "--initial-branch=main"], work)
        git(["config", "user.name", "Synthetic Seeder"], work)
        git(["config", "user.email", "synthetic@example.invalid"], work)
        (work / "README.md").write_text("# Entirely synthetic demo repository\n")
        if name == "kestrel-device-sw" and not empty:
            shutil.copytree(DATA / "code", work, dirs_exist_ok=True)
            for file in (work / "kestrel").glob("*.py"):
                if file.name != "__init__.py":
                    file.unlink()
            (work / "architecture.yaml").write_text(
                yaml.safe_dump(
                    [a for a in artifacts if a["type"] in ("component", "adr")], sort_keys=False
                )
            )
        elif not empty:
            shutil.copyfile(DATA / "sad_v1.md", work / "sad.md")
        git(["add", "."], work)
        git(["commit", "-m", "Synthetic repository seed"], work)
        git(["remote", "add", "origin", str(bare)], work)
        git(["push", "origin", "main"], work)
        if name == "kestrel-dhf-docs" and not empty:
            git(["tag", "sad-v1"], work)
            git(["push", "origin", "sad-v1"], work)
        # Transport guard independently enforces read-only device history.
        hook = bare / "hooks/pre-receive"
        hook.write_text(
            "#!/bin/sh\n"
            + (
                'if [ "$DHF_GIT_ROLE" != "seed" ]; then\n'
                ' echo "Device repository is read-only to product" >&2\n exit 1\nfi\n'
                if name == "kestrel-device-sw"
                else "exit 0\n"
            )
        )
        hook.chmod(0o755)
        repos.append(
            {
                "id": name,
                "name": name,
                "remoteUrl": str(bare),
                "defaultBranch": "refs/heads/main",
                "project": {"id": "kestrel", "name": "Kestrel"},
            }
        )
    history = yaml.safe_load((DATA / "history.yaml").read_text())
    prs = []
    for entry in [] if empty else history:
        prs.append(commit_entry(root, entry, ids))
    runs = []
    for a in [] if empty else artifacts:
        if a["type"] != "test_run":
            continue
        rid = int(a["id"].split("-")[1])
        results = []
        for r in artifacts:
            if r["type"] == "test_result" and r["attributes"]["run"] == a["id"]:
                results.append(
                    {
                        "id": int(r["id"].split("-")[-1]),
                        "testCase": {"id": str(ids[r["attributes"]["test_case"]])},
                        "outcome": r["attributes"]["outcome"],
                        "completedDate": r["attributes"]["completed_at"],
                        "comment": payload(r),
                        "associatedBugs": [
                            {"id": ids[e["dst"]]}
                            for e in dataset["links"]
                            if e["src"] == r["id"] and e["type"] == "reports_defect"
                        ],
                        "testCaseTitle": r["title"],
                        "testRun": {"id": str(rid)},
                    }
                )
        runs.append(
            {
                "id": rid,
                "name": a["title"] + (" retest" if a["attributes"]["is_retest"] else ""),
                "buildConfiguration": {"platform": a["attributes"]["environment"]},
                "state": "Completed",
                "completedDate": a["attributes"]["completed_at"],
                "comment": payload(a),
                "results": results,
            }
        )
    state = {
        "items": items,
        "ids": ids,
        "repositories": repos,
        "prs": prs,
        "runs": runs,
        "scenarios": [],
    }
    write_state(root, state)
    return state


def commit_entry(root: Path, entry: dict, ids: dict, scenario: dict | None = None) -> dict:
    work = root / "seed-kestrel-device-sw"
    for path in entry["files"]:
        dest = work / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = (DATA / "code" / path).read_text()
        if scenario:
            text = text.replace(scenario["old"], scenario["new"])
        dest.write_text(text)
    message = entry["title"] + " " + " ".join(f"AB#{ids[r]}" for r in entry["workitems"])
    git(["add", "."], work)
    git(["commit", "-m", message], work)
    sha = git(["rev-parse", "HEAD"], work)
    git(["push", "origin", "main"], work)
    return {
        "pullRequestId": entry["native_id"],
        "repository": {"id": "kestrel-device-sw"},
        "title": entry["title"],
        "description": message,
        "status": "completed",
        "sourceRefName": f"refs/heads/fixture/{entry['native_id']}",
        "targetRefName": "refs/heads/main",
        "lastMergeCommit": {"commitId": sha},
        "workitems": [ids[r] for r in entry["workitems"]],
        "statuses": [],
    }


def apply_scenario(name: str, root: Path = ROOT) -> dict:
    if name != "change_1":
        raise ValueError("Unknown scenario")
    state = read_state(root)
    if name in state["scenarios"]:
        return {"already_applied": name}
    scenario = yaml.safe_load((DATA / "scenarios" / f"{name}.yaml").read_text())
    edit = scenario["edit"]
    native = state["ids"][edit["id"]]
    item = state["items"][str(native)]["current"]
    item["fields"]["System.Description"] = edit["body"] + '\nDHF-META:{"synthetic": true}'
    item["fields"][
        yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())["fields"]["acceptance_criteria"]
    ] = edit["attributes"]["acceptance_criteria"]
    item["rev"] += 1
    item["fields"]["System.ChangedDate"] = scenario["run"]["completed_at"]
    state["items"][str(native)]["history"].append(copy.deepcopy(item))
    state["prs"].append(commit_entry(root, scenario["pr"], state["ids"], scenario["code"]))
    run = scenario["run"]
    state["runs"].append(
        {
            "id": run["id"],
            "name": "Release 1.1 occlusion retest",
            "state": "Completed",
            "completedDate": run["completed_at"],
            "buildConfiguration": {"platform": "Synthetic bench simulator"},
            "comment": 'Occlusion change verification\nDHF-META:{"synthetic": true}',
            "results": [
                {
                    "id": 21,
                    "testCase": {"id": str(state["ids"][run["test_case"]])},
                    "testRun": {"id": str(run["id"])},
                    "testCaseTitle": "Result for TC-021",
                    "outcome": run["outcome"],
                    "completedDate": run["completed_at"],
                    "associatedBugs": [],
                    "comment": "Result for TC-021",
                }
            ],
        }
    )
    state["scenarios"].append(name)
    write_state(root, state)
    return {"applied": name, "revision": item["rev"], "pr": 8, "run": 3}


def auth_token(header: str) -> str:
    try:
        return base64.b64decode(header.removeprefix("Basic ")).decode().split(":", 1)[1]
    except (ValueError, UnicodeError, IndexError):
        return ""


def merge_docs_pr(pr_id: int, root: Path = ROOT) -> dict:
    """Test tooling simulates the repo owner's merge; never called by the product."""
    state = read_state(root)
    pr = next(p for p in state["prs"] if p["pullRequestId"] == pr_id)
    if pr["repository"]["id"] != "kestrel-dhf-docs" or pr["status"] != "active":
        raise ValueError("Only active docs PRs can be merged by this test tool")
    work = root / "seed-kestrel-dhf-docs"
    git(["fetch", "origin", pr["sourceRefName"]], work)
    git(["checkout", "main"], work)
    git(["merge", "--ff-only", "FETCH_HEAD"], work)
    git(["push", "origin", "main"], work)
    pr["status"] = "completed"
    pr["lastMergeCommit"] = {"commitId": git(["rev-parse", "HEAD"], work)}
    write_state(root, state)
    return {
        "pullRequestId": pr_id,
        "status": "completed",
        "commit": pr["lastMergeCommit"]["commitId"],
    }
