"""Native seed-write/metadata routes. Handler authenticates before entering this module."""

import copy
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote

from mock_ado.state import git, write_state

if TYPE_CHECKING:
    from mock_ado.server import Handler


def seed_route(
    h: "Handler", method: str, path: str, query: dict, data: dict | list, state: dict, base: str
) -> bool:
    root = h.server.root

    def send(value: object, status: int = 200) -> bool:
        h.respond(value, status)
        return True

    def collection(values: list) -> bool:
        return send({"count": len(values), "value": values})

    if path.endswith("/wit/fields") and method == "GET":
        fields = sorted({f for e in state["items"].values() for f in e["current"]["fields"]})
        return collection([{"referenceName": f, "name": f.rsplit(".", 1)[-1]} for f in fields])
    if path.endswith("/wit/workitemtypes") and method == "GET":
        return collection(
            [
                {"name": t}
                for t in sorted(
                    {e["current"]["fields"]["System.WorkItemType"] for e in state["items"].values()}
                )
            ]
        )
    if path.endswith("/wit/workitemrelationtypes") and method == "GET":
        return collection(
            [
                {"referenceName": t, "name": t.rsplit(".", 1)[-1]}
                for t in sorted(
                    {
                        r["rel"]
                        for e in state["items"].values()
                        for r in e["current"].get("relations", [])
                    }
                )
            ]
        )
    if path.endswith("/_apis/connectionData") and method == "GET":
        return send({"authenticatedUser": {"id": "synthetic-seeder"}})
    match = re.search(r"/wit/workitems/(\$[^/]+|\d+)$", path)
    if match and method in ("POST", "PATCH"):
        if h.headers.get("Content-Type", "").split(";", 1)[0] != "application/json-patch+json":
            return send({"message": "JSON Patch required"}, 415)
        if (
            any(
                op.get("path") in ("/fields/System.ChangedDate", "/fields/System.CreatedDate")
                for op in data
            )
            and query.get("bypassRules", ["false"])[0].lower() != "true"
        ):
            return send({"message": "System dates require bypassRules permission"}, 400)
        create = match[1].startswith("$")
        if create != (method == "POST"):
            return send({"message": "Invalid operation"}, 400)
        native = max((int(id) for id in state["items"]), default=0) + 1 if create else int(match[1])
        value = (
            {
                "id": native,
                "rev": 0,
                "fields": {
                    "System.Id": native,
                    "System.WorkItemType": unquote(match[1][1:]),
                    "System.State": "Active",
                    "System.ChangedDate": datetime.now(UTC).isoformat(),
                },
                "relations": [],
            }
            if create
            else copy.deepcopy(state["items"][str(native)]["current"])
        )
        value["fields"]["System.ChangedDate"] = datetime.now(UTC).isoformat()
        for operation in data:
            op, pointer = operation["op"], operation["path"]
            if op == "test" and pointer == "/rev":
                if operation["value"] != value["rev"]:
                    return send({"message": "Revision conflict"}, 409)
            elif pointer.startswith("/fields/") and op in ("add", "replace", "remove"):
                key = pointer[8:].replace("~1", "/").replace("~0", "~")
                if op == "remove":
                    value["fields"].pop(key, None)
                else:
                    value["fields"][key] = operation["value"]
            elif pointer == "/relations/-" and op == "add":
                relation = operation["value"]
                target = relation["url"].rsplit("/", 1)[1]
                if target not in state["items"]:
                    return send({"message": "Relation target missing"}, 400)
                value["relations"].append(relation)
            else:
                return send({"message": "Unsupported JSON Patch operation"}, 400)
        value["rev"] += 1
        value["url"] = base + f"/_apis/wit/workitems/{native}"
        value["_links"] = {"html": {"href": base + f"/_workitems/edit/{native}?rev={value['rev']}"}}
        state["items"].setdefault(str(native), {"history": []})
        state["items"][str(native)]["current"] = value
        state["items"][str(native)]["history"].append(copy.deepcopy(value))
        for tag in value["fields"].get("System.Tags", "").split(";"):
            if tag.strip().startswith("DHF:"):
                state["ids"][tag.strip()[4:]] = native
        write_state(root, state)
        return send(value, 200)
    if path.endswith("/test/runs") and method == "POST":
        run = {**data, "id": max((r["id"] for r in state["runs"]), default=0) + 1, "results": []}
        state["runs"].append(run)
        write_state(root, state)
        return send({k: v for k, v in run.items() if k != "results"})
    match = re.search(r"/test/runs/(\d+)(/results)?$", path)
    if match and method in ("POST", "PATCH"):
        run = next(r for r in state["runs"] if r["id"] == int(match[1]))
        if match[2]:
            if method == "POST":
                values = []
                for result in data:
                    value = {
                        **result,
                        "id": max((r["id"] for r in run["results"]), default=0) + 1,
                        "testRun": {"id": str(run["id"])},
                    }
                    run["results"].append(value)
                    values.append(value)
            else:
                values = []
                for update in data:
                    value = next(r for r in run["results"] if r["id"] == update["id"])
                    value.update(update)
                    values.append(value)
            write_state(root, state)
            return collection(values)
        run.update(data)
        write_state(root, state)
        return send({k: v for k, v in run.items() if k != "results"})
    if path.endswith("/git/repositories") and method == "POST":
        name = data["name"]
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise ValueError("Invalid repository name")
        bare = (root / "git" / (name + ".git")).resolve()
        git(["init", "--bare", "--initial-branch=main", str(bare)], root)
        work = root / ("seed-" + name)
        work.mkdir()
        git(["init", "--initial-branch=main"], work)
        git(["config", "user.name", "Synthetic Seeder"], work)
        git(["config", "user.email", "synthetic@example.invalid"], work)
        git(["remote", "add", "origin", str(bare)], work)
        if name == "kestrel-device-sw":
            hook = bare / "hooks/pre-receive"
            hook.write_text('#!/bin/sh\nif [ "$DHF_GIT_ROLE" != "seed" ]; then exit 1; fi\n')
            hook.chmod(0o755)
        repo = {
            "id": name,
            "name": name,
            "remoteUrl": str(bare),
            "defaultBranch": "refs/heads/main",
        }
        state["repositories"].append(repo)
        write_state(root, state)
        return send(repo, 201)
    match = re.search(r"/git/repositories/([^/]+)/(refs|items|pushes)$", path)
    if match:
        repo = next(
            r for r in state["repositories"] if r["id"] == match[1] or r["name"] == match[1]
        )
        bare = root / "git" / (repo["name"] + ".git")
        if match[2] == "refs" and method == "GET":
            lines = git(["for-each-ref", "--format=%(refname) %(objectname)"], bare).splitlines()
            prefix = query.get("filter", [""])[0]
            return collection(
                [
                    {"name": n, "objectId": oid}
                    for line in lines
                    for n, oid in [line.split()]
                    if n.removeprefix("refs/").startswith(prefix)
                ]
            )
        if match[2] == "refs" and method == "POST":
            values = []
            for update in data:
                git(["check-ref-format", update["name"]], bare)
                git(
                    ["update-ref", update["name"], update["newObjectId"], update["oldObjectId"]],
                    bare,
                )
                values.append({**update, "success": True, "updateStatus": "succeeded"})
            return collection(values)
        if match[2] == "items" and method == "GET":
            p = query.get("path", [""])[0].lstrip("/")
            ref = query.get("versionDescriptor.version", ["main"])[0]
            try:
                text = git(["show", ref + ":" + p], bare, strip=False)
            except Exception:
                return send({"message": "File not found"}, 404)
            return send({"path": "/" + p, "content": text})
        if match[2] == "pushes" and method == "POST":
            update = data["refUpdates"][0]
            ref = update["name"]
            if not ref.startswith("refs/heads/"):
                return send({"message": "Only branch pushes supported"}, 400)
            work = root / ("seed-" + repo["name"])
            git(["fetch", "origin"], work)
            old = update["oldObjectId"]
            branch = ref.removeprefix("refs/heads/")
            if old == "0" * 40:
                git(["checkout", "--orphan", branch], work)
            else:
                git(["checkout", "--detach", old], work)
                git(["checkout", "-B", branch], work)
            commits = []
            for commit in data["commits"]:
                for change in commit["changes"]:
                    p = PurePosixPath(change["item"]["path"].lstrip("/"))
                    if ".." in p.parts or ".git" in p.parts or "\\" in str(p):
                        raise ValueError("Unsafe source path")
                    dest = work / str(p)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if change["changeType"] == "delete":
                        dest.unlink()
                    else:
                        dest.write_text(change["newContent"]["content"])
                git(["add", "."], work)
                git(["commit", "-m", commit["comment"]], work)
                commits.append({"commitId": git(["rev-parse", "HEAD"], work)})
            git(["push", "origin", "HEAD:" + ref], work)
            return send(
                {
                    "commits": commits,
                    "refUpdates": [{**update, "newObjectId": commits[-1]["commitId"]}],
                },
                201,
            )
    match = re.search(r"/git/repositories/([^/]+)/pullrequests/(\d+)$", path)
    if match and method == "PATCH":
        pr = next(p for p in state["prs"] if p["pullRequestId"] == int(match[2]))
        if data.get("status") == "completed":
            repo = next(r for r in state["repositories"] if r["id"] == match[1])
            work = root / ("seed-" + repo["name"])
            git(["fetch", "origin"], work)
            git(["checkout", "main"], work)
            git(
                ["merge", "--ff-only", "origin/" + pr["sourceRefName"].removeprefix("refs/heads/")],
                work,
            )
            git(["push", "origin", "main"], work)
            pr["lastMergeCommit"] = {"commitId": git(["rev-parse", "HEAD"], work)}
        pr.update(data)
        write_state(root, state)
        return send({k: v for k, v in pr.items() if k not in ("workitems", "statuses")})
    return False
