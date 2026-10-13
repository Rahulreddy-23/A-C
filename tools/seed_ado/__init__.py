"""Explicitly authorized synthetic source writes; never imported by the product."""

import json
from graphlib import TopologicalSorter
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
import typer
import yaml

from dhf.config import setting
from dhf.ingest.native import fixture_item

app = typer.Typer(help="Seed synthetic Kestrel evidence into a dedicated ADO project.")


def work_plan(dataset: dict, mapping: dict) -> list[dict]:
    kinds = {
        v
        for value in mapping["work_item_types"].values()
        for v in (value.values() if isinstance(value, dict) else [value])
    }
    nodes = {a["id"]: a for a in dataset["artifacts"] if a["type"] in kinds}
    dependencies = {
        id: {e["dst"] for e in dataset["links"] if e["src"] == id and e["dst"] in nodes}
        for id in sorted(nodes)
    }
    return [nodes[id] for id in TopologicalSorter(dependencies).static_order()]


class Seeder:
    def __init__(self, base: str, project: str, token: str, confirm_org: str) -> None:
        self.base = base.rstrip("/")
        parsed = urlsplit(self.base)
        org = (
            parsed.hostname.split(".")[0]
            if parsed.hostname.endswith(".visualstudio.com")
            else parsed.path.rstrip("/").rsplit("/", 1)[-1]
        )
        if not confirm_org or confirm_org != org:
            raise ValueError("--confirm-org must match the configured organization")
        if not token or token == setting("APP_ADO_PAT", "mock-app-token"):
            raise ValueError("A separate SEED_ADO_PAT is required")
        self.project = project
        self.url = self.base + "/" + quote(project, safe="")
        self.client = httpx.Client(base_url=self.url, auth=("", token), timeout=30)

    def close(self) -> None:
        self.client.close()

    def request(
        self, method: str, path: str, data: dict | list | None = None, patch: bool = False
    ) -> dict:
        result = self.client.request(
            method,
            path + ("&" if "?" in path else "?") + "api-version=7.1",
            json=data,
            headers={"Content-Type": "application/json-patch+json"} if patch else {},
        )
        if result.is_error:
            raise ValueError(
                f"Seeder request failed (HTTP {result.status_code}); "
                "check process and seed permissions"
            )
        return result.json()

    def collection(self, path: str) -> list[dict]:
        values, skip = [], 0
        while True:
            sep = "&" if "?" in path else "?"
            result = self.request("GET", path + f"{sep}$top=100&$skip={skip}")["value"]
            values.extend(result)
            if len(result) < 100:
                return values
            skip += len(result)

    def push(self, repo: str, files: dict, branch: str, message: str) -> dict | None:
        endpoint = f"/_apis/git/repositories/{repo}"
        refs = self.collection(endpoint + "/refs")
        ref = "refs/heads/" + branch
        old = next((r["objectId"] for r in refs if r["name"] == ref), None)
        base = old or next(
            (r["objectId"] for r in refs if r["name"] == "refs/heads/main"), "0" * 40
        )
        changes = []
        for name, text in sorted(files.items()):
            response = self.client.get(
                endpoint + "/items",
                params={
                    "path": "/" + name,
                    "includeContent": "true",
                    "versionDescriptor.version": branch if old else "main",
                    "api-version": "7.1",
                },
            )
            if response.status_code not in (200, 404):
                raise ValueError("Cannot inspect seed repository file")
            if response.status_code == 200 and response.json().get("content") == text:
                continue
            changes.append(
                {
                    "changeType": "edit" if response.status_code == 200 else "add",
                    "item": {"path": "/" + name},
                    "newContent": {"content": text, "contentType": "rawtext"},
                }
            )
        if not changes:
            return None
        return self.request(
            "POST",
            endpoint + "/pushes",
            {
                "refUpdates": [{"name": ref, "oldObjectId": base}],
                "commits": [{"comment": message, "changes": changes}],
            },
        )

    def seed(self, dry_run: bool = False, data_root: Path = Path("data/synthetic")) -> dict:
        dataset = yaml.safe_load((data_root / "evidence.yaml").read_text())
        mapping = yaml.safe_load(Path("specs/ado_mapping.yaml").read_text())
        planned = work_plan(dataset, mapping)
        ids = [
            i["id"]
            for i in self.request(
                "POST",
                "/_apis/wit/wiql",
                {
                    "query": "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '"
                    + self.project.replace("'", "''")
                    + "'"
                },
            )["workItems"]
        ]
        existing = []
        for start in range(0, len(ids), 200):
            existing += self.request(
                "POST",
                "/_apis/wit/workitemsbatch",
                {"ids": ids[start : start + 200], "$expand": "Relations"},
            )["value"]
        native = {}
        for item in existing:
            for tag in item["fields"].get(mapping["fields"]["tags"], "").split(";"):
                if tag.strip().startswith(mapping["id_tag_prefix"]):
                    canonical = tag.strip()[len(mapping["id_tag_prefix"]) :]
                    if canonical in native:
                        raise ValueError("Duplicate seed identity; review project before writing")
                    native[canonical] = item["id"]
        result = {
            "dry_run": dry_run,
            "work_items_created": 0,
            "runs_created": 0,
            "results_created": 0,
            "prs_created": 0,
            "git_pushes": 0,
        }
        if dry_run:
            return {
                **result,
                "work_items_to_create": sum(a["id"] not in native for a in planned),
                "planned_runs": 2,
                "planned_prs": 7,
                "note": "No writes; repository/run changes inspected during confirmed execution",
            }
        for artifact in planned:
            if artifact["id"] in native:
                continue
            item = fixture_item(artifact, 0, mapping)
            fields = {
                k: v
                for k, v in item["fields"].items()
                if k not in ("System.Id", "System.WorkItemType")
            }
            history = artifact["attributes"].get("requirement_history", [])
            if history:
                fields[mapping["fields"]["changed_at"]] = history[0]["changed_at"]
            operations = [
                {"op": "add", "path": "/fields/" + k, "value": v} for k, v in fields.items()
            ]
            operations += [
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": mapping["relations"][e["type"]],
                        "url": self.url + f"/_apis/wit/workitems/{native[e['dst']]}",
                        "attributes": {"comment": "Synthetic Kestrel seed"},
                    },
                }
                for e in dataset["links"]
                if e["src"] == artifact["id"]
                and e["dst"] in native
                and e["type"] in mapping["relations"]
            ]
            created = self.request(
                "POST",
                "/_apis/wit/workitems/$" + quote(item["fields"]["System.WorkItemType"], safe=""),
                operations,
                patch=True,
            )
            native[artifact["id"]] = created["id"]
            for revision in history[1:]:
                self.request(
                    "PATCH",
                    f"/_apis/wit/workitems/{created['id']}",
                    [
                        {
                            "op": "add",
                            "path": "/fields/" + mapping["fields"]["changed_at"],
                            "value": revision["changed_at"],
                        }
                    ],
                    patch=True,
                )
            result["work_items_created"] += 1
        repo_names = {r["name"]: r["id"] for r in self.collection("/_apis/git/repositories")}
        for name in ("kestrel-device-sw", "kestrel-dhf-docs"):
            if name not in repo_names:
                repo_names[name] = self.request("POST", "/_apis/git/repositories", {"name": name})[
                    "id"
                ]
        repo = repo_names["kestrel-device-sw"]
        history = yaml.safe_load((data_root / "history.yaml").read_text())
        module_paths = {p for h in history for p in h["files"]}
        bootstrap = {
            str(p.relative_to(data_root / "code")): p.read_text()
            for p in (data_root / "code").rglob("*")
            if p.is_file()
            and p.suffix in (".py", ".yaml", ".txt")
            and str(p.relative_to(data_root / "code")) not in module_paths
        }
        bootstrap["architecture.yaml"] = yaml.safe_dump(
            [a for a in dataset["artifacts"] if a["type"] in ("component", "adr")], sort_keys=False
        )
        if self.push(repo, bootstrap, "main", "Synthetic Kestrel bootstrap"):
            result["git_pushes"] += 1
        existing_prs = self.collection(
            f"/_apis/git/repositories/{repo}/pullrequests?searchCriteria.status=all"
        )
        for entry in history:
            marker = "Seed:" + entry["id"]
            pr = next((p for p in existing_prs if marker in p.get("description", "")), None)
            if pr and pr["status"] == "completed":
                continue
            branch = "seed/" + entry["id"].lower()
            files = {p: (data_root / "code" / p).read_text() for p in entry["files"]}
            pushed = self.push(
                repo,
                files,
                branch,
                entry["title"] + " " + " ".join(f"AB#{native[r]}" for r in entry["workitems"]),
            )
            if pushed:
                result["git_pushes"] += 1
            if pr is None:
                pr = self.request(
                    "POST",
                    f"/_apis/git/repositories/{repo}/pullrequests",
                    {
                        "sourceRefName": "refs/heads/" + branch,
                        "targetRefName": "refs/heads/main",
                        "title": entry["title"],
                        "description": marker,
                        "workItemRefs": [{"id": str(native[r])} for r in entry["workitems"]],
                    },
                )
                result["prs_created"] += 1
            refs = self.collection(f"/_apis/git/repositories/{repo}/refs")
            commit = next(r["objectId"] for r in refs if r["name"] == "refs/heads/" + branch)
            self.request(
                "PATCH",
                f"/_apis/git/repositories/{repo}/pullrequests/{pr['pullRequestId']}",
                {
                    "status": "completed",
                    "lastMergeSourceCommit": {"commitId": commit},
                    "completionOptions": {"mergeStrategy": "rebase", "deleteSourceBranch": False},
                },
            )
        if self.push(
            repo_names["kestrel-dhf-docs"],
            {"sad.md": (data_root / "sad_v1.md").read_text()},
            "main",
            "Synthetic SAD baseline",
        ):
            result["git_pushes"] += 1
        docs_endpoint = f"/_apis/git/repositories/{repo_names['kestrel-dhf-docs']}"
        refs = self.collection(docs_endpoint + "/refs")
        if not any(r["name"] == "refs/tags/sad-v1" for r in refs):
            head = next(r["objectId"] for r in refs if r["name"] == "refs/heads/main")
            self.request(
                "POST",
                docs_endpoint + "/refs",
                [{"name": "refs/tags/sad-v1", "oldObjectId": "0" * 40, "newObjectId": head}],
            )
        runs = self.collection("/_apis/test/runs")
        for run in (a for a in dataset["artifacts"] if a["type"] == "test_run"):
            name = run["title"] + (" retest" if run["attributes"]["is_retest"] else "")
            current = next((r for r in runs if r["name"] == name), None)
            if current is None:
                current = self.request(
                    "POST",
                    "/_apis/test/runs",
                    {
                        "name": name,
                        "state": "InProgress",
                        "isAutomated": False,
                        "buildConfiguration": {"platform": run["attributes"]["environment"]},
                        "comment": run["body"] + '\nDHF-META:{"synthetic": true}',
                    },
                )
                result["runs_created"] += 1
            endpoint = f"/_apis/test/runs/{current['id']}"
            existing_results = self.collection(endpoint + "/results")
            rows = []
            for r in (
                a
                for a in dataset["artifacts"]
                if a["type"] == "test_result" and a["attributes"]["run"] == run["id"]
            ):
                case = str(native[r["attributes"]["test_case"]])
                if any(str(v["testCase"]["id"]) == case for v in existing_results):
                    continue
                rows.append(
                    {
                        "testCase": {"id": case},
                        "testCaseTitle": r["title"],
                        "outcome": r["attributes"]["outcome"],
                        "state": "Completed",
                        "completedDate": r["attributes"]["completed_at"],
                        "comment": r["body"],
                        "associatedBugs": [
                            {"id": native[e["dst"]]}
                            for e in dataset["links"]
                            if e["src"] == r["id"] and e["type"] == "reports_defect"
                        ],
                    }
                )
            if rows:
                self.request("POST", endpoint + "/results", rows)
                result["results_created"] += len(rows)
            if current.get("state") != "Completed":
                self.request(
                    "PATCH",
                    endpoint,
                    {"state": "Completed", "completedDate": run["attributes"]["completed_at"]},
                )
        return result


@app.command()
def seed(confirm_org: str = typer.Option(..., "--confirm-org"), dry_run: bool = False) -> None:
    seeder = Seeder(
        setting("ADO_BASE_URL", "http://localhost:8089/kestrel-org"),
        setting("ADO_PROJECT", "Kestrel"),
        setting("SEED_ADO_PAT", "mock-seed-token"),
        confirm_org,
    )
    try:
        typer.echo(json.dumps(seeder.seed(dry_run), indent=2))
    finally:
        seeder.close()
