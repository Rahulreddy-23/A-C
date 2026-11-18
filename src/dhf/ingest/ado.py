"""Azure DevOps REST 7.1 adapter; no knowledge of mock administration."""

import hashlib
import ipaddress
import os
import re
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import httpx
import yaml

from dhf.config import setting
from dhf.ingest.code import PythonExtractor
from dhf.ingest.native import (
    native_record,
    normalize_result,
    normalize_run,
    normalize_workitem,
    workitem_kind,
)
from dhf.models.evidence import validate_graph

READ_POSTS = ("/_apis/wit/wiql", "/_apis/wit/workitemsbatch")
WORKITEM_URL = re.compile(r"/_apis/wit/workItems/(\d+)$", re.I)
SEED_ID = re.compile(r"(?:_workitems/edit/|/workitems/|[?&]workitem=)(\d+)", re.I)
DEFAULT_FOLLOW = (
    "System.LinkTypes.Hierarchy-Forward",
    "System.LinkTypes.Hierarchy-Reverse",
    "Microsoft.VSTS.Common.TestedBy-Forward",
    "Microsoft.VSTS.Common.TestedBy-Reverse",
)
# ADO shows every work-item link on both ends under these paired reference names.
RECIPROCAL = {
    "System.LinkTypes.Hierarchy-Forward": "System.LinkTypes.Hierarchy-Reverse",
    "System.LinkTypes.Hierarchy-Reverse": "System.LinkTypes.Hierarchy-Forward",
    "Microsoft.VSTS.Common.TestedBy-Forward": "Microsoft.VSTS.Common.TestedBy-Reverse",
    "Microsoft.VSTS.Common.TestedBy-Reverse": "Microsoft.VSTS.Common.TestedBy-Forward",
    "System.LinkTypes.Dependency-Forward": "System.LinkTypes.Dependency-Reverse",
    "System.LinkTypes.Dependency-Reverse": "System.LinkTypes.Dependency-Forward",
    "System.LinkTypes.Related": "System.LinkTypes.Related",
}


class ReadOnlyViolation(PermissionError):
    """Raised before any non-read request can leave the process."""


def is_loopback_host(host: str) -> bool:
    """Only names that cannot resolve elsewhere: 'localhost' and loopback addresses."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def read_only_mode(base: str) -> bool:
    """Real organizations are read-only unless the owner explicitly opts a docs repo in."""
    value = setting("ADO_READ_ONLY", "auto").strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    return not is_loopback_host(urlsplit(base).hostname or "")


def remote_is_read_only(url: str) -> bool:
    """Git remotes follow the organization rule; local paths (the mock) are not remote."""
    parts = urlsplit(url)
    if parts.scheme in ("", "file") or not parts.hostname:
        return False
    return read_only_mode(url)


def seed_ids(text: str) -> tuple[set[int], int]:
    """Work-item IDs from a seed file: ADO URLs in any form, or a leading ID per line.

    Returns the IDs and the number of non-blank, non-comment lines that held none."""
    ids, unparsed = set(), 0
    for line in (raw.strip() for raw in text.splitlines()):
        if not line or line.startswith("#"):
            continue
        found = SEED_ID.findall(line) or re.findall(r"^(\d+)\b", line)
        ids.update(int(i) for i in found)
        unparsed += not found
    return ids, unparsed


def load_scope(path: str = "") -> dict:
    """Optional ingest scope (ADO_SCOPE YAML); without one the whole project is read.

    seed_files hold ADO work-item URLs or bare IDs, one per line, resolved relative to
    the scope file. A scope that names seeds but yields none is an error, never a silent
    whole-project read."""
    path = path or setting("ADO_SCOPE", "")
    if not path:
        return {}
    scope = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    ids = {int(i) for i in scope.get("seed_ids") or []}
    unparsed = 0
    for name in scope.get("seed_files") or []:
        found, missed = seed_ids((Path(path).parent / name).read_text(encoding="utf-8"))
        ids |= found
        unparsed += missed
    declared = "seed_ids" in scope or "seed_files" in scope
    if declared and not ids and not scope.get("wiql"):
        raise ValueError(f"ADO_SCOPE {path} names seeds but none could be read")
    release = scope.get("release")
    if release is not None and not isinstance(release, str):
        # YAML reads `release: 1.10` as the number 1.1; a label must stay as written.
        raise ValueError(f'ADO_SCOPE release must be quoted text, e.g. release: "{release}"')
    documents = scope.get("documents")
    if documents:  # design documents that supply the architecture ADO does not hold
        spec: dict = {"folder": documents} if isinstance(documents, str) else dict(documents)
        spec["folder"] = str(Path(path).parent / spec["folder"])
        spec["profile"] = (
            str(Path(path).parent / spec["profile"])
            if spec.get("profile")
            else "specs/doc_import/dhf_documents.yaml"
        )
        spec.setdefault("types", ["component", "software_unit"])
        scope["documents"] = spec  # existence is checked when an ingest starts
    return {**scope, "seed_ids": sorted(ids), "unparsed_seed_lines": unparsed}


def reciprocal(link: str) -> str:
    """The other end of an ADO link type: ADO shows each link on both work items."""
    if link in RECIPROCAL:
        return RECIPROCAL[link]
    for end, other in (("-Forward", "-Reverse"), ("-Reverse", "-Forward")):
        if link.endswith(end):
            return link[: -len(end)] + other
    return link


def subcommand(args: list[str]) -> str:
    """The git subcommand after any leading `-c name=value` options."""
    index = 0
    while index < len(args) and args[index].startswith("-"):
        index += 2 if args[index] == "-c" else 1
    return args[index] if index < len(args) else ""


def git_command(args: list[str], cwd: Path, token: str = "", strip: bool = True) -> str:
    """Git auth stays in environment/askpass, never remote URL or command arguments.

    Configured credential helpers are disabled so git neither uses a stored (possibly
    write-capable) credential nor saves the PAT, and pushes to a read-only organization
    are refused here, whatever code path asks for them."""
    if subcommand(args) == "push" and remote_is_read_only(
        git_command(["remote", "get-url", "origin"], cwd)
    ):
        raise ReadOnlyViolation("Read-only mode: refusing git push to this organization")
    helper = Path("out/git-askpass.sh").resolve()
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        '#!/bin/sh\ncase "$1" in\n*Username*) printf "%s" "dhf";;\n'
        '*) printf "%s" "$DHF_GIT_PAT";;\nesac\n',
        encoding="utf-8",
        newline="\n",
    )
    helper.chmod(0o700)
    env = dict(
        os.environ,
        GIT_ASKPASS=str(helper),
        GIT_TERMINAL_PROMPT="0",
        DHF_GIT_PAT=token,
        DHF_GIT_ROLE="app",
        GCM_INTERACTIVE="never",
    )
    # No stored credentials; no CRLF conversion, so Windows checkouts keep the exact bytes.
    result = subprocess.run(
        ["git", "-c", "credential.helper=", "-c", "core.autocrlf=false", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError("Git operation failed; check repository access and branch configuration")
    return result.stdout.strip() if strip else result.stdout


def clone_location(root: Path, remote: str) -> Path:
    """Keep clones from different configured source repos isolated."""
    if root.exists() and git_command(["remote", "get-url", "origin"], root) != remote:
        root = root.with_name(root.name + "-" + hashlib.sha256(remote.encode()).hexdigest()[:12])
    if root.exists() and git_command(["remote", "get-url", "origin"], root) != remote:
        raise ValueError("Clone path belongs to another configured repository")
    return root


class ADO:
    def __init__(
        self,
        base_url: str | None = None,
        project: str | None = None,
        token: str | None = None,
        scope: dict | None = None,
        *,
        trust_env: bool = True,
        mapping: dict | None = None,
    ) -> None:
        self.base = (
            base_url or setting("ADO_BASE_URL", "http://localhost:8089/kestrel-org")
        ).rstrip("/")
        self.project = project or setting("ADO_PROJECT", "Kestrel")
        self.token = token or setting("APP_ADO_PAT", "mock-app-token")
        self.url = self.base + "/" + quote(self.project, safe="")
        self.read_only = read_only_mode(self.base)
        self.scope = load_scope() if scope is None else scope
        self.report: Counter = Counter()
        if self.scope.get("unparsed_seed_lines"):
            self.report["seed lines without a work-item ID"] = self.scope["unparsed_seed_lines"]
        self.client = httpx.Client(
            base_url=self.url,
            auth=("", self.token),
            timeout=60,
            trust_env=trust_env,
            event_hooks={"request": [self.guard]},
        )
        self.mapping = (
            mapping
            if mapping is not None
            else yaml.safe_load(
                Path(setting("ADO_MAPPING", "specs/ado_mapping.yaml")).read_text(encoding="utf-8")
            )
        )

    def close(self) -> None:
        self.client.close()

    @property
    def seeded(self) -> bool:
        """A scope with seeds or WIQL reads only those items; any other scope reads all."""
        return bool(self.scope.get("seed_ids") or self.scope.get("wiql"))

    def guard(self, request: httpx.Request) -> None:
        """Transport-level last line of defence: read-only mode sends reads only."""
        path = request.url.path
        if request.method == "GET" or (request.method == "POST" and path.endswith(READ_POSTS)):
            return
        if self.read_only:
            raise ReadOnlyViolation(f"Read-only mode blocked {request.method} {path}")

    def request(
        self, method: str, path: str, data: dict | None = None, params: dict | None = None
    ) -> dict:
        docs_repo = setting("ADO_DOCS_REPO", "kestrel-dhf-docs")
        docs_write = method == "POST" and path.startswith(
            "/_apis/git/repositories/" + docs_repo + "/pullrequests"
        )
        if method != "GET" and not (method == "POST" and path in READ_POSTS) and not docs_write:
            raise ValueError("Product forbids source-system writes")
        if docs_write and self.read_only:
            raise ReadOnlyViolation(
                "Read-only mode: docs-repo writes are disabled for this organization "
                "(set ADO_READ_ONLY=0 only for a docs repository you own)"
            )
        query = {"api-version": "7.1", **(params or {})}
        response = self.client.request(method, path, json=data, params=query)
        for attempt in range(3):  # ADO throttling: honour Retry-After, then give up
            if response.status_code not in (429, 503):
                break
            time.sleep(min(float(response.headers.get("Retry-After", 2**attempt)), 30))
            response = self.client.request(method, path, json=data, params=query)
        if response.status_code in (203, 401):
            reason = unquote(response.headers.get("x-tfs-serviceerror", "")) or "sign-in required"
            raise PermissionError(f"ADO rejected APP_ADO_PAT: {reason}")
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
        limit = int(self.scope.get("max_items", setting("ADO_MAX_ITEMS", "5000")))
        if self.seeded:
            seeds = set(self.scope.get("seed_ids", []))
            if self.scope.get("wiql"):
                seeds |= set(self.query_ids(self.scope["wiql"], limit))
            items = self.expand(seeds, self.scope.get("follow", {}), limit)
            if since:
                items = [i for i in items if i["fields"].get("System.ChangedDate", "") > since]
            return items
        query = (
            "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '"
            + self.project.replace("'", "''")
            + "'"
        )
        if since:
            query += " AND [System.ChangedDate] > '" + since.replace("'", "''") + "'"
        return self.fetch(self.query_ids(query, limit))

    def query_ids(self, query: str, limit: int) -> list[int]:
        found = self.request("POST", "/_apis/wit/wiql", {"query": query}, {"$top": limit + 1})
        ids = [i["id"] for i in found["workItems"]]
        if len(ids) > limit:
            raise ValueError(
                f"Query matched more than {limit} work items; set ADO_SCOPE "
                "(seed_ids, seed_files or wiql) or raise max_items"
            )
        return ids

    def fetch(self, ids: list[int]) -> list[dict]:
        """Batch-read work items with relations; deleted or inaccessible IDs are omitted."""
        result = []
        for start in range(0, len(ids), 200):
            page = self.request(
                "POST",
                "/_apis/wit/workitemsbatch",
                {"ids": ids[start : start + 200], "$expand": "Relations", "errorPolicy": "Omit"},
            )["value"]
            result.extend(item for item in page if item)
        if len(result) < len(ids):
            self.report["work items unavailable"] += len(ids) - len(result)
        for item in result:
            web = f"{self.url}/_workitems/edit/{item['id']}"
            item.setdefault("_links", {"html": {"href": web}})
        return result

    def expand(self, seeds: set[int], follow: dict, limit: int) -> list[dict]:
        """Seed work items plus linked items up to `depth` hops along the chosen link types."""
        depth = int(follow.get("depth", 1))
        relations = self.followed(follow)
        items: dict[int, dict] = {}
        frontier = set(seeds)
        for level in range(depth + 1):
            frontier -= items.keys()
            if len(items) + len(frontier) > limit:
                raise ValueError(
                    f"Scope expansion exceeds max_items={limit} at depth {level}; "
                    "reduce follow.depth or follow.relations"
                )
            fetched = self.fetch(sorted(frontier))
            items.update((item["id"], item) for item in fetched)
            if level == depth:
                break
            frontier = {
                int(match[1])
                for item in fetched
                for relation in item.get("relations", [])
                if relation["rel"] in relations and (match := WORKITEM_URL.search(relation["url"]))
            }
        return [items[i] for i in sorted(items)]

    def followed(self, follow: dict) -> set[str]:
        """Link types scope expansion follows: an explicit list ([] follows none), else the
        default."""
        chosen = follow.get("relations")
        return self.follow_default() if chosen is None else set(chosen)

    def follow_default(self) -> set[str]:
        """Parent/child and test links, plus both ends of every link type the mapping traces
        (e.g. Dependency between requirements and specifications); Related is too broad."""
        mapped = {v for v in self.mapping["relations"].values() if v != "System.LinkTypes.Related"}
        return set(DEFAULT_FOLLOW) | mapped | {reciprocal(r) for r in mapped}

    def runs_read(self) -> bool:
        plans = self.scope.get("test_plans")
        return bool(plans) if plans is not None else not self.seeded

    def test_runs(self) -> list[dict]:
        """Runs of the scope's test plans; every run for a whole-project read; none for a
        seeded scope without plans (reported, since a real project can hold thousands)."""
        plans = self.scope.get("test_plans")
        if plans is None:
            if not self.seeded:
                return self.collection("/_apis/test/runs")
            self.report["test runs not read (no test_plans in scope)"] += 1
            return []
        return [
            run for plan in plans for run in self.collection("/_apis/test/runs", {"planId": plan})
        ]

    def ingest(self, clone_root: Path = Path("out/clones")) -> dict:
        documents = self.scope.get("documents")
        if documents:  # fail before the (long) ADO read, never after it
            if not Path(documents["folder"]).is_dir():
                raise ValueError(f"ADO_SCOPE documents folder not found: {documents['folder']}")
            if not Path(documents["profile"]).is_file():
                raise ValueError(f"ADO_SCOPE documents profile not found: {documents['profile']}")
        retrieved = datetime.now(UTC).isoformat()
        items = self.workitems()
        mapping = self.mapping
        artifacts = []
        native_ids = {}
        item_kinds = {}
        history_enabled = self.scope.get("history", True)
        for item in items:
            # Only requirement history feeds change tracking; other kinds skip the request.
            needs_history = workitem_kind(item["fields"], mapping) == "software_req"
            history = (
                self.collection(f"/_apis/wit/workitems/{item['id']}/revisions")
                if history_enabled and needs_history and item.get("rev", 1) > 1
                else [item]
            )
            artifact = normalize_workitem(item, history, mapping, retrieved)
            if artifact is None:
                self.report["unmapped " + item["fields"].get("System.WorkItemType", "?")] += 1
                continue
            if artifact["id"] in native_ids.values():  # e.g. a copied item keeps its Spec ID
                artifact["attributes"]["duplicate_document_id"] = artifact["id"]
                artifact["id"] = f"ADO-{item['id']}"
                self.report["duplicate document IDs (kept as ADO-<id>)"] += 1
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
        outside_bugs: list[tuple[str, str]] = []
        # The scope's release labels only runs of its own test plans whose names carry none.
        scope_release = str(self.scope.get("release") or "") if self.scope.get("test_plans") else ""
        if self.scope.get("release") and not scope_release:
            self.report["scope release ignored (no test_plans)"] += 1
        for raw_run in self.test_runs():
            run = normalize_run(raw_run, mapping, retrieved, self.url, scope_release)
            kept = False  # in a seeded scope a run is evidence only through in-scope results
            for result in self.collection(f"/_apis/test/runs/{raw_run['id']}/results"):
                case = (result.get("testCase") or {}).get("id")
                if case is None:
                    self.report["test results without a test case"] += 1
                    continue
                if str(case) not in native_ids:
                    self.report["test results outside scope"] += 1
                    continue
                artifact = normalize_result(result, run, native_ids, retrieved, self.url)
                if not kept:
                    artifacts.append(run)
                    kept = True
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
                    if str(bug["id"]) not in native_ids:
                        outside_bugs.append((artifact["id"], str(bug["id"])))
                        continue
                    links.append(
                        edge(
                            artifact["id"],
                            native_ids[str(bug["id"])],
                            "reports_defect",
                            "Associated bug",
                        )
                    )
            if not kept and not self.seeded:
                artifacts.append(run)  # a whole-project read keeps empty or aborted runs
            elif not kept:
                self.report["test runs without in-scope results"] += 1
            elif scope_release and not re.search(mapping["release_pattern"], raw_run["name"]):
                self.report["test runs labelled with the scope release"] += 1
        # A failed result's defect is evidence of that result: read it even when the scope did
        # not reach it, or the result would be reported as having no defect (G05).
        missing = sorted({int(bug) for _, bug in outside_bugs})
        for item in self.fetch(missing) if missing else []:
            artifact = normalize_workitem(item, [item], mapping, retrieved)
            if artifact is not None and artifact["id"] not in native_ids.values():
                artifacts.append(artifact)
                native_ids[str(item["id"])] = artifact["id"]
                self.report["associated bugs read outside scope"] += 1
        for result_id, bug in outside_bugs:
            if bug in native_ids:
                links.append(edge(result_id, native_ids[bug], "reports_defect", "Associated bug"))
        repo_name = (
            self.scope.get("repository", setting("ADO_DEVICE_REPO", ""))
            if self.scope
            else setting("ADO_DEVICE_REPO", "kestrel-device-sw")
        )
        if repo_name:
            self.code_evidence(repo_name, clone_root, retrieved, native_ids, artifacts, links)
        else:
            self.report["code evidence not configured"] += 1
        by_id = {a["id"]: a for a in artifacts}
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
        if not (repo_name and self.runs_read()):
            # Declare the link classes this configuration can carry, so rules on links it
            # never reads (code without a repository, results without test plans) are not
            # assessable instead of a gap per artifact (ADR-041).
            # Work-item links only ever join work items, so a mapped link never makes a rule
            # about code changes or results assessable (G02 stays blind without a repository).
            work_items = {
                kind
                for value in mapping["work_item_types"].values()
                for kind in (value.values() if isinstance(value, dict) else [value])
            }
            # A seeded scope sees only the link types its expansion follows; a link it
            # never follows is not readable, so its rules are not assessable (no false gaps).
            followed = self.followed(self.scope.get("follow", {})) if self.seeded else None

            def readable(link_type: str) -> bool:
                return followed is None or bool({link_type, reciprocal(link_type)} & followed)

            classes = {
                f"{k}:{peer}"
                for k, v in mapping["relations"].items()
                if v != "System.LinkTypes.Related" and readable(v)
                for peer in work_items
            }
            for pair in mapping.get("related_pairs", []):  # typed: a shared name, a given peer
                if readable("System.LinkTypes.Related"):
                    classes |= {f"{pair['type']}:{pair['src']}", f"{pair['type']}:{pair['dst']}"}
            if mapping.get("area_components") or repo_name or documents:
                classes.add("allocated_to")
            if repo_name:
                classes.add("implements")
            if self.runs_read():
                classes |= {"executes", "reports_defect"}
            for artifact in artifacts:
                artifact["attributes"]["link_classes"] = sorted(classes)
        graph = {"artifacts": artifacts, "links": links}
        if documents:
            graph = self.merge_documents(graph, documents)
        return validate_graph(graph)

    def merge_documents(self, graph: dict, spec: dict) -> dict:
        """Add the architecture the scope's design documents record (ADR-044): software
        items, units and their allocations, read locally. ADO stays the source for every
        requirement, specification and test it holds."""
        from dhf.ingest.documents import import_folder, merge_baseline

        held = frozenset(a["id"] for a in graph["artifacts"])
        baseline, summary = import_folder(Path(spec["folder"]), Path(spec["profile"]), held)
        merged, report = merge_baseline(
            graph, baseline, spec["types"], summary.get("external_links", [])
        )
        # Everything `dhf import-docs` would report, so incomplete or wrong-issue design
        # evidence (unreadable files, duplicates, older issues) is never silent here.
        self.report["design documents read"] += len(summary["imported_files"])
        self.report["design documents: older issues not read"] += len(summary["older_issues"])
        self.report["design documents: duplicate IDs ignored"] += len(summary["duplicates_ignored"])
        for note, count in summary["notes"].items():
            self.report["design documents: " + note] += count
        self.report.update(report)
        return merged

    def code_evidence(
        self,
        repo_name: str,
        clone_root: Path,
        retrieved: str,
        native_ids: dict,
        artifacts: list[dict],
        links: list[dict],
    ) -> None:
        """Clone the source repo read-only, extract code evidence and linked PRs."""
        repo = next(
            (r for r in self.collection("/_apis/git/repositories") if r["name"] == repo_name),
            None,
        )
        if repo is None:
            raise ValueError(f"Source repository {repo_name!r} not found in {self.project}")
        clone_root.mkdir(parents=True, exist_ok=True)
        clone = clone_location(clone_root / repo_name, repo["remoteUrl"])
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
        by_id = {a["id"]: a for a in artifacts}
        inside = [e for e in extracted["links"] if e["src"] in by_id and e["dst"] in by_id]
        outside = len(extracted["links"]) - len(inside)
        if outside:
            self.report["code links to items outside scope"] += outside
        links.extend(inside)
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
                self.mapping.get("default_component"),
            )
            attrs = {"synthetic": synthetic} | ({"component": component} if component else {})
            artifacts.append(
                native_record(
                    pr_id,
                    "code_change",
                    pr["title"],
                    pr["title"],
                    attrs,
                    self.url + f"/_git/{repo_name}/pullrequest/{pr['pullRequestId']}",
                    str(pr["pullRequestId"]),
                    retrieved,
                )
            )
            links.extend(edge(pr_id, r, "implements", "ADO PR work-item reference") for r in reqs)


def edge(src: str, dst: str, kind: str, evidence: str) -> dict:
    return {"src": src, "dst": dst, "type": kind, "origin": "explicit", "evidence": evidence}
