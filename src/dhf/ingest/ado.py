"""Azure DevOps REST 7.1 adapter; no knowledge of mock administration."""

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml

from dhf.config import setting
from dhf.ingest.code import PythonExtractor
from dhf.models.evidence import validate_graph


def git_command(args: list[str], cwd: Path, token: str = "") -> str:
    """Git auth stays in environment/askpass, never remote URL or command arguments."""
    helper = Path("out/git-askpass.sh").resolve()
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        '#!/bin/sh\ncase "$1" in\n*Username*) printf "%s" "dhf";;\n'
        '*) printf "%s" "$DHF_GIT_PAT";;\nesac\n'
    )
    helper.chmod(0o700)
    env = dict(
        os.environ,
        GIT_ASKPASS=str(helper),
        GIT_TERMINAL_PROMPT="0",
        DHF_GIT_PAT=token,
        DHF_GIT_ROLE="app",
    )
    result = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Git operation failed; check repository access and branch configuration")
    return result.stdout.strip()


class ADO:
    def __init__(
        self, base_url: str | None = None, project: str | None = None, token: str | None = None
    ) -> None:
        self.base = (
            base_url or setting("ADO_BASE_URL", "http://localhost:8089/kestrel-org")
        ).rstrip("/")
        self.project = project or setting("ADO_PROJECT", "Kestrel")
        self.token = token or setting("APP_ADO_PAT", "mock-app-token")
        self.url = self.base + "/" + quote(self.project, safe="")
        self.client = httpx.Client(base_url=self.url, auth=("", self.token), timeout=30)
        self.mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())

    def close(self) -> None:
        self.client.close()

    def request(
        self, method: str, path: str, data: dict | None = None, params: dict | None = None
    ) -> dict:
        if method != "GET" and not (
            method == "POST"
            and (
                path in ("/_apis/wit/wiql", "/_apis/wit/workitemsbatch")
                or path.startswith(
                    "/_apis/git/repositories/"
                    + setting("ADO_DOCS_REPO", "kestrel-dhf-docs")
                    + "/pullrequests"
                )
            )
        ):
            raise ValueError("Product forbids source-system writes")
        response = self.client.request(
            method, path, json=data, params={"api-version": "7.1", **(params or {})}
        )
        response.raise_for_status()
        return response.json()

    def collection(self, path: str, params: dict | None = None) -> list[dict]:
        values = []
        skip = 0
        while True:
            result = self.request(
                "GET", path, params={**(params or {}), "$top": 100, "$skip": skip}
            )
            page = result["value"]
            values.extend(page)
            if len(page) < 100:
                break
            skip += len(page)
        return values

    def workitems(self, since: str | None = None) -> list[dict]:
        query = (
            "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '"
            + self.project.replace("'", "''")
            + "'"
        )
        if since:
            query += " AND [System.ChangedDate] > '" + since.replace("'", "''") + "'"
        ids = [
            i["id"] for i in self.request("POST", "/_apis/wit/wiql", {"query": query})["workItems"]
        ]
        result = []
        for start in range(0, len(ids), 200):
            result.extend(
                self.request(
                    "POST",
                    "/_apis/wit/workitemsbatch",
                    {"ids": ids[start : start + 200], "$expand": "Relations"},
                )["value"]
            )
        return result

    def ingest(self, clone_root: Path = Path("out/clones")) -> dict:
        retrieved = datetime.now(UTC).isoformat()
        items = self.workitems()
        mapping = self.mapping
        fields = mapping["fields"]
        artifacts = []
        native_ids = {}
        for item in items:
            tags = [t.strip() for t in item["fields"].get(fields["tags"], "").split(";")]
            stable = next(
                (
                    t[len(mapping["id_tag_prefix"]) :]
                    for t in tags
                    if t.startswith(mapping["id_tag_prefix"])
                ),
                f"ADO-{item['id']}",
            )
            native_ids[str(item["id"])] = stable
            kind = mapping["work_item_types"].get(item["fields"]["System.WorkItemType"])
            if isinstance(kind, dict):
                kind = next((kind[t] for t in tags if t in kind), "software_req")
            if kind is None:
                continue
            body, attrs = metadata(
                item["fields"].get(fields["body"], ""), mapping["metadata_marker"]
            )
            attrs.setdefault("state", item["fields"].get(fields["state"], "Active")) if kind in (
                "defect",
                "action_item",
            ) else None
            artifacts.append(
                {
                    "id": stable,
                    "type": kind,
                    "title": item["fields"][fields["title"]],
                    "body": body,
                    "attributes": attrs,
                    "source": {
                        "system": "ado",
                        "url": item["_links"]["html"]["href"],
                        "native_id": str(item["id"]),
                        "revision": str(item["rev"]),
                        "retrieved_at": retrieved,
                    },
                }
            )
        links = []
        reverse = {v: k for k, v in mapping["relations"].items() if v != "System.LinkTypes.Related"}
        for item in items:
            for relation in item.get("relations", []):
                target = relation["url"].rsplit("/", 1)[1]
                name = relation.get("attributes", {}).get("name", "")
                kind = reverse.get(relation["rel"])
                if relation["rel"] == "System.LinkTypes.Related" and name.startswith(
                    mapping["related_name_prefix"]
                ):
                    kind = name[len(mapping["related_name_prefix"]) :]
                if kind and target in native_ids:
                    links.append(
                        edge(
                            native_ids[str(item["id"])],
                            native_ids[target],
                            kind,
                            "ADO relation " + relation["url"],
                        )
                    )
        for run in self.collection("/_apis/test/runs"):
            run_id = f"RUN-{run['id']}"
            body, attrs = metadata(run.get("comment", run["name"]), mapping["metadata_marker"])
            attrs.setdefault("completed_at", run.get("completedDate", ""))
            artifacts.append(
                record(
                    run_id,
                    "test_run",
                    run["name"],
                    body,
                    attrs,
                    self.url + f"/_apis/test/runs/{run['id']}",
                    str(run["id"]),
                    retrieved,
                )
            )
            for result in self.collection(f"/_apis/test/runs/{run['id']}/results"):
                result_id = f"RES-{run['id']}-{int(result['id']):03}"
                tc = native_ids[result["testCase"]["id"]]
                body, attrs = metadata(
                    result.get("comment", result.get("testCaseTitle", "")),
                    mapping["metadata_marker"],
                )
                attrs.update({"test_case": tc, "outcome": result["outcome"], "run": run_id})
                artifacts.append(
                    record(
                        result_id,
                        "test_result",
                        result.get("testCaseTitle", tc),
                        body,
                        attrs,
                        self.url + f"/_apis/test/runs/{run['id']}/results/{result['id']}",
                        str(result["id"]),
                        retrieved,
                    )
                )
                links.extend(
                    [
                        edge(result_id, tc, "executes", "Test result reference"),
                        edge(result_id, run_id, "derives_from", "Test run reference"),
                    ]
                )
                for bug in result.get("associatedBugs", []):
                    links.append(
                        edge(
                            result_id,
                            native_ids[str(bug["id"])],
                            "reports_defect",
                            "Associated bug",
                        )
                    )
        repo_name = setting("ADO_DEVICE_REPO", "kestrel-device-sw")
        repo = next(r for r in self.collection("/_apis/git/repositories") if r["name"] == repo_name)
        clone_root.mkdir(parents=True, exist_ok=True)
        clone = clone_root / repo_name
        if not clone.exists():
            git_command(["clone", repo["remoteUrl"], str(clone.resolve())], clone_root, self.token)
        else:
            git_command(["fetch", "origin"], clone, self.token)
            git_command(
                [
                    "reset",
                    "--hard",
                    "origin/"
                    + repo.get("defaultBranch", "refs/heads/main").removeprefix("refs/heads/"),
                ],
                clone,
                self.token,
            )
        files = {
            p: git_command(["show", "HEAD:" + p], clone) + "\n"
            for p in git_command(["ls-tree", "-r", "--name-only", "HEAD"], clone).splitlines()
            if p.endswith((".py", ".txt", ".yaml"))
        }
        extracted = PythonExtractor().extract(files, self.url + "/_git/" + repo_name, retrieved)
        synthetic = bool(files.get("architecture.yaml")) and all(
            a["attributes"].get("synthetic") is True for a in extracted["artifacts"]
        )
        for a in extracted["artifacts"]:
            path = a["attributes"].get("path")
            if path:
                commit = git_command(["log", "-1", "--format=%H", "--", path], clone)
                a["source"]["url"] = (
                    self.url + "/_git/" + repo_name + "?path=/" + path + "&version=GC" + commit
                )
        artifacts.extend(extracted["artifacts"])
        links.extend(extracted["links"])
        by_id = {a["id"]: a for a in artifacts}
        for pr in self.collection(
            f"/_apis/git/repositories/{repo['id']}/pullrequests", {"searchCriteria.status": "all"}
        ):
            pr_id = f"PR-{pr['pullRequestId']}"
            refs = self.collection(
                f"/_apis/git/repositories/{repo['id']}/pullrequests/{pr['pullRequestId']}/workitems"
            )
            reqs = [native_ids[str(r["id"])] for r in refs if str(r["id"]) in native_ids]
            components = [by_id[r]["attributes"].get("component") for r in reqs if r in by_id]
            component = next((c for c in components if c), "COMP-06")
            artifacts.append(
                record(
                    pr_id,
                    "code_change",
                    pr["title"],
                    pr["title"],
                    {"synthetic": synthetic, "component": component},
                    self.url + f"/_git/{repo_name}/pullrequest/{pr['pullRequestId']}",
                    str(pr["pullRequestId"]),
                    retrieved,
                )
            )
            links.extend(edge(pr_id, r, "implements", "ADO PR work-item reference") for r in reqs)
        for a in extracted["artifacts"]:
            if a["type"] != "software_unit":
                continue
            messages = git_command(["log", "--format=%B", "--", a["attributes"]["path"]], clone)
            linked = {native_ids[n] for n in re.findall(r"AB#(\d+)", messages) if n in native_ids}
            links.extend(
                edge(a["id"], r, "implements", "AB# commit reference") for r in sorted(linked)
            )
        # Git-only component allocation is supplied by requirement metadata when not a WIT relation.
        links.extend(
            edge(
                a["id"],
                a["attributes"]["component"],
                "allocated_to",
                "Requirement component metadata",
            )
            for a in artifacts
            if a["type"] == "software_req" and a["attributes"].get("component") in by_id
        )
        return validate_graph({"artifacts": artifacts, "links": links})


def metadata(text: str, marker: str) -> tuple[str, dict]:
    if "\n" + marker in text:
        body, raw = text.split("\n" + marker, 1)
        return body, json.loads(raw)
    return text, {}


def edge(src: str, dst: str, kind: str, evidence: str) -> dict:
    return {"src": src, "dst": dst, "type": kind, "origin": "explicit", "evidence": evidence}


def record(
    id: str, kind: str, title: str, body: str, attrs: dict, url: str, native: str, retrieved: str
) -> dict:
    return {
        "id": id,
        "type": kind,
        "title": title,
        "body": body,
        "attributes": attrs,
        "source": {
            "system": "ado",
            "url": url,
            "native_id": native,
            "revision": "1",
            "retrieved_at": retrieved,
        },
    }
