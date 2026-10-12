"""Azure DevOps REST 7.1 adapter; no knowledge of mock administration."""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx
import yaml

from dhf.config import setting
from dhf.ingest.code import PythonExtractor
from dhf.ingest.native import native_record, normalize_result, normalize_run, normalize_workitem
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
        artifacts = []
        native_ids = {}
        item_kinds = {}
        for item in items:
            history = self.collection(f"/_apis/wit/workitems/{item['id']}/revisions")
            artifact = normalize_workitem(item, history, mapping, retrieved)
            if artifact is not None:
                artifacts.append(artifact)
                native_ids[str(item["id"])] = artifact["id"]
                item_kinds[str(item["id"])] = artifact["type"]
        links = []
        reverse = {v: k for k, v in mapping["relations"].items() if v != "System.LinkTypes.Related"}
        for item in items:
            src = str(item["id"])
            if src not in native_ids:
                continue
            for relation in item.get("relations", []):
                target = relation["url"].rsplit("/", 1)[1]
                if target not in native_ids:
                    continue
                kind = reverse.get(relation["rel"])
                if relation["rel"] == "System.LinkTypes.Related":
                    kind = next(
                        (
                            pair["type"]
                            for pair in mapping["related_pairs"]
                            if pair["src"] == item_kinds[src] and pair["dst"] == item_kinds[target]
                        ),
                        None,
                    )
                if kind:
                    links.append(
                        edge(
                            native_ids[src],
                            native_ids[target],
                            kind,
                            "ADO relation " + relation["url"],
                        )
                    )
        for raw_run in self.collection("/_apis/test/runs"):
            run = normalize_run(raw_run, mapping, retrieved, self.url)
            artifacts.append(run)
            for result in self.collection(f"/_apis/test/runs/{raw_run['id']}/results"):
                artifact = normalize_result(result, run, native_ids, retrieved, self.url)
                artifacts.append(artifact)
                links.extend(
                    [
                        edge(
                            artifact["id"],
                            artifact["attributes"]["test_case"],
                            "executes",
                            "Test result reference",
                        ),
                        edge(artifact["id"], run["id"], "derives_from", "Test run reference"),
                    ]
                )
                for bug in result.get("associatedBugs", []):
                    links.append(
                        edge(
                            artifact["id"],
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
            branch = repo.get("defaultBranch", "refs/heads/main").removeprefix("refs/heads/")
            git_command(["reset", "--hard", "origin/" + branch], clone, self.token)
        paths = git_command(["ls-tree", "-r", "--name-only", "HEAD"], clone).splitlines()
        files = {
            p: git_command(["show", "HEAD:" + p], clone) + "\n"
            for p in paths
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
            component = next(
                (
                    by_id[r]["attributes"].get("component")
                    for r in reqs
                    if by_id[r]["attributes"].get("component")
                ),
                "COMP-06",
            )
            artifacts.append(
                native_record(
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
        links.extend(
            edge(
                a["id"],
                a["attributes"]["component"],
                "allocated_to",
                "Native AreaPath component mapping",
            )
            for a in artifacts
            if a["type"] == "software_req" and a["attributes"].get("component") in by_id
        )
        return validate_graph({"artifacts": artifacts, "links": links})


def edge(src: str, dst: str, kind: str, evidence: str) -> dict:
    return {"src": src, "dst": dst, "type": kind, "origin": "explicit", "evidence": evidence}
