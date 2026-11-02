import copy
import html
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dhf.config import setting
from mock_ado.state import ROOT, apply_scenario, auth_token, init, read_state, write_state

RECIPROCAL = {
    "System.LinkTypes.Hierarchy-Forward": "System.LinkTypes.Hierarchy-Reverse",
    "System.LinkTypes.Hierarchy-Reverse": "System.LinkTypes.Hierarchy-Forward",
    "Microsoft.VSTS.Common.TestedBy-Forward": "Microsoft.VSTS.Common.TestedBy-Reverse",
    "Microsoft.VSTS.Common.TestedBy-Reverse": "Microsoft.VSTS.Common.TestedBy-Forward",
    "System.LinkTypes.Related": "System.LinkTypes.Related",
}


class Server(ThreadingHTTPServer):
    def __init__(self, root: Path = ROOT, port: int = 8089, empty: bool = False) -> None:
        self.root = root
        self.lock = threading.RLock()
        init(root, empty=empty)
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        pass  # No request headers, tokens or payloads in logs.

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_PATCH(self) -> None:
        self.dispatch("PATCH")

    def do_DELETE(self) -> None:
        self.dispatch("DELETE")

    def respond(self, value: object, status: int = 200, is_html: bool = False) -> None:
        body = str(value).encode() if is_html else json.dumps(value).encode()
        self.send_response(status)
        self.send_header(
            "Content-Type", "text/html; charset=utf-8" if is_html else "application/json"
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def dispatch(self, method: str) -> None:
        with self.server.lock:
            try:
                self.route(method)
            except (KeyError, StopIteration):
                self.respond({"message": "Resource not found"}, 404)
            except (ValueError, json.JSONDecodeError):
                self.respond({"message": "Invalid or missing resource"}, 400)

    def route(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        token = auth_token(self.headers.get("Authorization", ""))
        app_pat = setting("APP_ADO_PAT", "mock-app-token")
        seed_pat = setting("SEED_ADO_PAT", "mock-seed-token")
        # Public browser pages contain exclusively synthetic data; REST always requires auth.
        if "/_apis/" in path or path.startswith("/_mock/"):
            if token not in (app_pat, seed_pat):
                return self.respond({"message": "Authentication required"}, 401)
            read_post = method == "POST" and path.endswith(("/wiql", "/workitemsbatch"))
            docs_write = (
                method == "POST" and "/git/repositories/kestrel-dhf-docs/pullrequests" in path
            )
            if token == app_pat and method != "GET" and not read_post and not docs_write:
                return self.respond(
                    {"message": "Product token is read-only outside docs repo"}, 403
                )
        state = read_state(self.server.root)
        base = f"http://127.0.0.1:{self.server.server_port}/kestrel-org/Kestrel"
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length)) if length else {}

        # ADO shows every work-item link on both ends (Tests / Tested By, Parent / Child).
        incoming: dict[str, list[dict]] = {}
        for source, entry in state["items"].items():
            for relation in entry["current"]["relations"]:
                target = re.search(r"/workitems/(\d+)$", "/" + relation["url"], re.I)
                if target and relation["rel"] in RECIPROCAL:
                    incoming.setdefault(target[1], []).append(
                        {"rel": RECIPROCAL[relation["rel"]], "url": f"_apis/wit/workitems/{source}"}
                    )

        def item_url(item: dict, expanded: bool = False) -> dict:
            value = copy.deepcopy(item)
            value["url"] = f"{base}/_apis/wit/workitems/{value['id']}"
            value["_links"] = {
                "html": {"href": f"{base}/_workitems/edit/{value['id']}?rev={value['rev']}"}
            }
            known = {(r["rel"], r["url"].rsplit("/", 1)[-1]) for r in value["relations"]}
            value["relations"] += [
                r
                for r in incoming.get(str(value["id"]), [])
                if (r["rel"], r["url"].rsplit("/", 1)[-1]) not in known
            ]
            for relation in value["relations"]:
                relation["url"] = (
                    relation["url"]
                    if relation["url"].startswith("http")
                    else f"{base}/" + relation["url"]
                )
            if not expanded:
                value.pop("relations", None)
            return value

        def public_pr(pr: dict) -> dict:
            return {k: v for k, v in pr.items() if k not in ("workitems", "statuses")}

        def collection(values: list) -> None:
            skip = int(query.get("$skip", ["0"])[0])
            top = int(query.get("$top", [str(len(values))])[0])
            page = values[skip : skip + top]
            self.respond({"count": len(page), "value": page})

        from mock_ado.seed_routes import seed_route

        if seed_route(self, method, path, query, data, state, base):
            return
        if path == "/_mock/state" and method == "GET":
            return self.respond(state)
        if path.startswith("/_mock/apply-scenario/") and method == "POST":
            return self.respond(apply_scenario(path.rsplit("/", 1)[1], self.server.root))
        if path == "/_mock/reset" and method == "POST":
            from mock_ado.cli import reset_root

            reset_root(self.server.root)
            return self.respond({"reset": True})
        if path.endswith("/wiql") and method == "POST":
            # Support product SELECT IDs + ChangedDate polling predicate.
            wiql = data.get("query", "")
            changed = re.search(r"\[System.ChangedDate\]\s*>\s*'([^']+)'", wiql)
            values = [entry["current"] for entry in state["items"].values()]
            if changed:
                values = [v for v in values if v["fields"]["System.ChangedDate"] > changed[1]]
            return self.respond(
                {
                    "queryType": "flat",
                    "queryResultType": "workItem",
                    "asOf": "2026-10-12T18:00:00Z",
                    "columns": [],
                    "workItems": [
                        {"id": v["id"], "url": f"{base}/_apis/wit/workitems/{v['id']}"}
                        for v in values
                    ],
                }
            )
        if path.endswith("/workitemsbatch") and method == "POST":
            if len(data["ids"]) > 200:
                return self.respond({"message": "Maximum batch size 200"}, 400)
            expanded = str(data.get("$expand", "")).lower() in ("relations", "all")
            omit = str(data.get("errorPolicy", "")).lower() == "omit"
            missing = [i for i in data["ids"] if str(i) not in state["items"]]
            if missing and not omit:
                return self.respond({"message": f"Work item {missing[0]} does not exist"}, 404)
            return collection(
                [
                    item_url(state["items"][str(i)]["current"], expanded)
                    if str(i) in state["items"]
                    else None
                    for i in data["ids"]
                ]
            )
        match = re.search(r"/workitems/(\d+)(/revisions)?(?:/(\d+))?$", path)
        if match and method == "GET":
            entry = state["items"].get(match[1])
            if entry is None:
                return self.respond({"message": "Work item not found"}, 404)
            expanded = query.get("$expand", [""])[0].lower() in ("relations", "all")
            if match[2] and not match[3]:
                return collection([item_url(v, expanded) for v in entry["history"]])
            value = (
                next(v for v in entry["history"] if v["rev"] == int(match[3]))
                if match[3]
                else entry["current"]
            )
            return self.respond(item_url(value, expanded))
        if "/_workitems/edit/" in path:
            native = path.rsplit("/", 1)[1]
            entry = state["items"].get(native)
            if not entry:
                return self.respond("Not found", 404, True)
            rev = int(query.get("rev", [str(entry["current"]["rev"])])[0])
            item = next(v for v in entry["history"] if v["rev"] == rev)
            return self.respond(
                "<h1>"
                + html.escape(item["fields"]["System.Title"])
                + "</h1><pre>"
                + html.escape(json.dumps(item_url(item, True), indent=2))
                + "</pre><h2>Revision history</h2>"
                + "".join(f'<a href="?rev={v["rev"]}">r{v["rev"]}</a> ' for v in entry["history"]),
                is_html=True,
            )
        if path.endswith("/test/runs") and method == "GET":
            plan = query.get("planId", [None])[0]
            return collection(
                [
                    {k: v for k, v in r.items() if k != "results"}
                    for r in state["runs"]
                    if plan is None or str(r.get("plan", {}).get("id")) == plan
                ]
            )
        match = re.search(r"/test/runs/(\d+)/results$", path)
        if match and method == "GET":
            return collection(next(r for r in state["runs"] if r["id"] == int(match[1]))["results"])
        if path.endswith("/git/repositories") and method == "GET":
            return collection(state["repositories"])
        match = re.search(
            r"/git/repositories/([^/]+)/pullrequests(?:/(\d+))?(?:/(workitems|statuses))?$", path
        )
        if match:
            repo, pr_id, suffix = match.groups()
            prs = [pr for pr in state["prs"] if pr["repository"]["id"] == repo]
            if pr_id:
                pr = next(p for p in prs if p["pullRequestId"] == int(pr_id))
                if suffix == "workitems" and method == "GET":
                    return collection(
                        [
                            {"id": str(i), "url": f"{base}/_apis/wit/workitems/{i}"}
                            for i in pr["workitems"]
                        ]
                    )
                if suffix == "statuses":
                    if method == "POST":
                        status = {"id": len(pr["statuses"]) + 1, **data}
                        pr["statuses"].append(status)
                        write_state(self.server.root, state)
                        return self.respond(status, 201)
                    return collection(pr["statuses"])
                return self.respond(public_pr(pr))
            if method == "POST":
                pr = {
                    "pullRequestId": max((p["pullRequestId"] for p in state["prs"]), default=0) + 1,
                    "repository": {"id": repo},
                    "status": "active",
                    "workitems": [int(w["id"]) for w in data.get("workItemRefs", [])],
                    "statuses": [],
                    **data,
                }
                pr["url"] = (
                    f"{base}/_apis/git/repositories/{repo}/pullrequests/{pr['pullRequestId']}"
                )
                pr["_links"] = {
                    "web": {"href": f"{base}/_git/{repo}/pullrequest/{pr['pullRequestId']}"}
                }
                state["prs"].append(pr)
                write_state(self.server.root, state)
                return self.respond(public_pr(pr), 201)
            status = query.get("searchCriteria.status", ["active"])[0]
            return collection(
                [public_pr(p) for p in prs if status == "all" or p["status"] == status]
            )
        match = re.search(r"/_git/([^/]+)/pullrequest/(\d+)$", path)
        if match:
            pr = next(
                p
                for p in state["prs"]
                if p["repository"]["id"] == match[1] and p["pullRequestId"] == int(match[2])
            )
            return self.respond(
                "<h1>"
                + html.escape(pr["title"])
                + "</h1><pre>"
                + html.escape(json.dumps(pr, indent=2))
                + "</pre>",
                is_html=True,
            )
        return self.respond({"message": "Not found"}, 404)
