"""Synthetic test tooling, kept separate from the product."""

import base64
import copy
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

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


def git(args: list[str], cwd: Path, seed: bool = True) -> str:
    env = dict(os.environ, DHF_GIT_ROLE="seed" if seed else "app")
    result = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def write_state(root: Path, state: dict) -> None:
    temp = root / "state.tmp"
    temp.write_text(json.dumps(state))
    temp.replace(root / "state.json")


def read_state(root: Path) -> dict:
    return json.loads((root / "state.json").read_text())


def payload(artifact: dict) -> str:
    return artifact["body"] + "\nDHF-META:" + json.dumps(artifact["attributes"], sort_keys=True)


def init(root: Path = ROOT) -> dict:
    if (root / "state.json").exists():
        return read_state(root)
    root.mkdir(parents=True, exist_ok=True)
    dataset = yaml.safe_load((DATA / "evidence.yaml").read_text())
    mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
    artifacts = dataset["artifacts"]
    eligible = [a for a in artifacts if a["type"] in WORK_TYPES]
    ids = {a["id"]: i for i, a in enumerate(eligible, 1)}
    items = {}
    for a in eligible:
        typ, tag = WORK_TYPES[a["type"]]
        attrs = a["attributes"]
        item = {
            "id": ids[a["id"]],
            "rev": attrs.get("revision", 1),
            "fields": {
                "System.Id": ids[a["id"]],
                "System.WorkItemType": typ,
                "System.Title": a["title"],
                "System.Description": payload(a),
                "System.Tags": f"{tag}; DHF:{a['id']}",
                "System.State": attrs.get("state", "Active"),
                "System.ChangedDate": attrs.get("changed_at", "2026-09-20T12:00:00Z"),
            },
            "relations": [],
        }
        for edge in dataset["links"]:
            if edge["src"] == a["id"] and edge["dst"] in ids:
                item["relations"].append(
                    {
                        "rel": mapping["relations"].get(edge["type"], "System.LinkTypes.Related"),
                        "url": f"_apis/wit/workitems/{ids[edge['dst']]}",
                        "attributes": {"name": "DHF:" + edge["type"]},
                    }
                )
        items[str(item["id"])] = {"current": item, "history": [copy.deepcopy(item)]}
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
        if name == "kestrel-device-sw":
            shutil.copytree(DATA / "code", work, dirs_exist_ok=True)
            for file in (work / "kestrel").glob("*.py"):
                if file.name != "__init__.py":
                    file.unlink()
            (work / "architecture.yaml").write_text(
                yaml.safe_dump(
                    [a for a in artifacts if a["type"] in ("component", "adr")], sort_keys=False
                )
            )
        else:
            shutil.copyfile(DATA / "sad_v1.md", work / "sad.md")
        git(["add", "."], work)
        git(["commit", "-m", "Synthetic repository seed"], work)
        git(["remote", "add", "origin", str(bare)], work)
        git(["push", "origin", "main"], work)
        if name == "kestrel-dhf-docs":
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
    for entry in history:
        prs.append(commit_entry(root, entry, ids))
    runs = []
    for a in artifacts:
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
                    }
                )
        runs.append(
            {
                "id": rid,
                "name": a["title"],
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
    old_body, meta = item["fields"]["System.Description"].split("\nDHF-META:", 1)
    attrs = json.loads(meta)
    attrs.update(edit["attributes"])
    attrs["revision"] = item["rev"] + 1
    attrs["changed_at"] = scenario["run"]["completed_at"]
    item["fields"]["System.Description"] = (
        edit["body"] + "\nDHF-META:" + json.dumps(attrs, sort_keys=True)
    )
    item["rev"] += 1
    item["fields"]["System.ChangedDate"] = scenario["run"]["completed_at"]
    state["items"][str(native)]["history"].append(copy.deepcopy(item))
    state["prs"].append(commit_entry(root, scenario["pr"], state["ids"], scenario["code"]))
    run = scenario["run"]
    attrs = {
        "synthetic": True,
        "release": run["release"],
        "completed_at": run["completed_at"],
        "environment": "Synthetic bench simulator",
        "is_retest": True,
    }
    result_attrs = {
        "synthetic": True,
        "release": run["release"],
        "completed_at": run["completed_at"],
        "test_case": run["test_case"],
        "outcome": run["outcome"],
        "run": "RUN-3",
        "verified_revision": 2,
    }
    state["runs"].append(
        {
            "id": run["id"],
            "name": "Occlusion change verification",
            "state": "Completed",
            "completedDate": run["completed_at"],
            "comment": "Occlusion change verification\nDHF-META:"
            + json.dumps(attrs, sort_keys=True),
            "results": [
                {
                    "id": 21,
                    "testCase": {"id": str(state["ids"][run["test_case"]])},
                    "testCaseTitle": "Result for TC-021",
                    "outcome": run["outcome"],
                    "completedDate": run["completed_at"],
                    "associatedBugs": [],
                    "comment": "Result for TC-021\nDHF-META:"
                    + json.dumps(result_attrs, sort_keys=True),
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
    except (ValueError, UnicodeError):
        return ""
