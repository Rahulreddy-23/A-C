"""Browser workspace and project API served only on the local loopback interface."""

import csv
import io
import json
import re
import secrets
import sqlite3
import sys
import threading
import traceback
from contextlib import closing
from http.cookies import CookieError, SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from pydantic import ValidationError

from dhf.config import setting
from dhf.llm import LLM
from dhf.render.explorer import create_explorer
from dhf.serve import LocalServer, LoopbackHandler
from dhf.trace import results_summary
from dhf.workspace import Workspace
from dhf.workspace.insights import dashboard, review_items
from dhf.workspace.sources import ConnectionInput, ProjectInput, WorkspaceError, now
from dhf.workspace.uploads import ALLOWED_TYPES, MAX_FILE_BYTES

EXPIRED_LINK = (
    "This access link was already used, or the workspace restarted. Press Ctrl+C in the"
    " window running dhf serve and start it again; it opens a new link."
)
ROUTE = re.compile(r"/api/projects/([a-zA-Z0-9_-]{1,64})(/[^?#]*)?")
JSON_LIMIT = 96 * 1024
CID = r"[0-9a-f]{32}"
DOWNLOADS = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown; charset=utf-8",
}


def project_id_for(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "project"
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def light(document: dict) -> dict:
    """A document row without its section claims and evidence, for lists and the dashboard."""
    draft = document["draft"]
    if draft is None:
        return document
    keep = ("version", "generated_at", "model", "readiness", "docx", "redline", "changed_sections")
    return {
        **document,
        "draft": {**{k: draft[k] for k in keep}, "sections": len(draft["sections"])},
    }


def cell_text(value: object) -> str:
    """Spreadsheet-safe text: source titles must never run as formulas."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def make_workspace_server(
    root: Path, project_id: str, owner: str, members: list[str], port: int = 8765
) -> tuple[ThreadingHTTPServer, dict[str, str]]:
    first = Workspace(root, project_id, owner, members)
    projects: dict[str, Workspace] = {project_id: first}
    grants = {secrets.token_urlsafe(32): actor for actor in (owner, *members)}
    sessions: dict[str, str] = {}
    jobs: dict[tuple[str, str], dict] = {}
    lock, drafting = threading.Lock(), threading.Lock()
    cookie_name = "dhf_session_" + secrets.token_hex(8)
    page = Path("specs/render/workspace.html").read_bytes()

    def discover() -> dict[str, Path]:
        """Workspaces this owner started, side by side with the first project's folder."""
        found = {}
        for path in sorted(root.parent.glob("*/workspace.sqlite")):
            try:
                with closing(sqlite3.connect(path)) as db:
                    row = db.execute("SELECT id, owner FROM projects").fetchone()
            except sqlite3.Error:
                continue  # not a readable workspace; never let one folder hide the rest
            if row and row[1] == owner:
                found[row[0]] = path.parent
        found[project_id] = root
        return found

    def open_project(pid: str) -> Workspace:
        with lock:
            if pid in projects:
                return projects[pid]
        path = discover().get(pid)
        if path is None:
            raise WorkspaceError(404, "Project route not found.")
        workspace = Workspace(path, pid, owner, members)
        with lock:
            return projects.setdefault(pid, workspace)

    def project_list(actor: str) -> list[dict]:
        """Every project with its documents' stages, for the projects dashboard."""
        rows = []
        for pid in discover():
            workspace = open_project(pid)
            details = workspace.details()
            documents = [
                {
                    "type": d["type"],
                    "stage": d["stage"],
                    "future": d["future"],
                    "version": d["draft"]["version"] if d["draft"] else None,
                    "blockers": len(d["draft"]["readiness"]["blockers"]) if d["draft"] else 0,
                    "approval": d["approvals"][0]["reference"] if d["approvals"] else None,
                }
                for d in workspace.documents(actor)
            ]
            provenance = workspace.provenance()
            rows.append(
                {
                    **details,
                    "name": details.get("name") or pid,
                    "documents": documents,
                    "fetched_at": provenance["fetched_at"],
                    "uploads": provenance["uploads"],
                }
            )
        return rows

    def start_draft(pid: str, workspace: Workspace, actor: str, doc: str, fresh: bool) -> dict:
        workspace.document(doc)
        if not drafting.acquire(blocking=False):
            raise WorkspaceError(409, "Another draft is being prepared. Try again when it ends.")
        provider = setting("DHF_PROVIDER", "mock")
        job = {"state": "running", "provider": provider, "started_at": now()}
        with lock:
            jobs[(pid, doc)] = job

        def work() -> None:
            try:
                outcome = {"state": "done", "result": workspace.draft(actor, doc, provider, fresh)}
            except WorkspaceError as error:
                outcome = {"state": "failed", "error": str(error), "action": error.action}
            except ValidationError:
                error = "The saved evidence did not validate. Fetch or upload the inputs again."
                outcome = {"state": "failed", "error": error}
            except ValueError as error:  # data errors and the AI data guard name the cause
                outcome = {"state": "failed", "error": str(error)}
            except Exception as error:
                # Type and location only: an exception message could carry source text.
                where = traceback.extract_tb(error.__traceback__)[-1]
                place = f"{Path(where.filename).name}:{where.lineno}"
                print(f"Drafting {doc} failed: {type(error).__name__} at {place}", file=sys.stderr)
                outcome = {"state": "failed", "error": "Drafting failed. Check inputs and AI."}
            finally:
                drafting.release()
            with lock:
                job.update(outcome, finished_at=now())

        threading.Thread(target=work, daemon=True).start()
        with lock:
            return dict(job)

    def ai_settings() -> dict:
        provider = setting("DHF_PROVIDER", "mock")
        llm = LLM(provider)
        try:
            budget = llm.budget_status()
        except ValueError:
            budget = {}
        return {
            "provider": provider,
            "model": llm.model,
            "real_data_approval": llm.real_data_approval,
            "copilot_mode": setting("DHF_COPILOT_MODE", "http")
            if provider == "copilotstudio"
            else "",
            "budget": budget,
        }

    class Handler(LoopbackHandler):
        def do_GET(self) -> None:
            self.dispatch()

        def do_POST(self) -> None:
            self.dispatch()

        def do_DELETE(self) -> None:
            self.dispatch()

        def dispatch(self) -> None:
            host = self.headers.get("Host")
            if host not in self.allowed():
                return self.json(403, {"error": "Unexpected host."})
            if self.command != "GET" and self.headers.get("Origin") != f"http://{host}":
                return self.json(403, {"error": "Request must come from this workspace page."})
            try:
                self.route()
            except WorkspaceError as error:
                self.json(error.status, {"error": str(error), "action": error.action})
            except ValidationError as error:
                field = next((str(e["loc"][0]) for e in error.errors() if e.get("loc")), "")
                named = f"Check the {field.replace('_', ' ')} field." if field else ""
                self.json(400, {"error": named or "Check the connection or input fields."})
            except (UnicodeError, json.JSONDecodeError):
                self.json(400, {"error": "Check the connection or input fields."})
            except Exception:
                self.json(500, {"error": "Could not process this workspace request."})

        def read_body(self, content_type: str, limit: int) -> bytes:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise WorkspaceError(400, "Invalid request length.") from None
            if length < 0 or self.headers.get("Transfer-Encoding"):
                raise WorkspaceError(400, "Invalid request length.")
            if length > limit:
                raise WorkspaceError(413, "Input exceeds the size limit.")
            if length and self.headers.get_content_type() != content_type:
                raise WorkspaceError(415, "Unsupported request format.")
            return self.rfile.read(length) if length else b""

        def json_body(self) -> dict:
            raw = self.read_body("application/json", JSON_LIMIT)
            result = json.loads(raw) if raw else {}
            if not isinstance(result, dict):
                raise WorkspaceError(400, "Expected a JSON object.")
            return result

        def login(self) -> None:
            grant = self.headers.get("Authorization", "").removeprefix("Bearer ")
            with lock:
                actor = grants.pop(grant, None)
                if actor is None:
                    raise WorkspaceError(401, EXPIRED_LINK)
                token = secrets.token_urlsafe(32)
                sessions[token] = actor
            body = json.dumps({"project_id": project_id}).encode()
            self.reply(
                200,
                body,
                "application/json",
                {"Set-Cookie": f"{cookie_name}={token}; Path=/; HttpOnly; SameSite=Strict"},
            )

        def actor(self) -> str:
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
            except CookieError:
                cookie = SimpleCookie()
            session = cookie.get(cookie_name)
            with lock:
                actor = sessions.get(session.value) if session else None
            if actor is None:
                raise WorkspaceError(401, EXPIRED_LINK)
            first.require_member(actor)
            return actor

        def route(self) -> None:
            if self.command == "GET" and self.path in {"/", "/index.html"}:
                return self.reply(200, page, "text/html; charset=utf-8")
            if self.path == "/api/session" and self.command == "POST":
                return self.login()
            actor = self.actor()
            if self.path == "/api/session" and self.command == "GET":
                return self.json(
                    200,
                    {
                        "project_id": project_id,
                        "actor": actor,
                        "profile": first.profile,
                        "file_types": sorted(ALLOWED_TYPES),
                    },
                )
            if self.path == "/api/projects":
                if self.command == "GET":
                    return self.json(200, {"projects": project_list(actor)})
                if self.command == "POST":
                    change = ProjectInput.model_validate(self.json_body())
                    # Folder names count too: a new project never opens an existing folder.
                    folders = {p.name for p in root.parent.iterdir() if p.is_dir()}
                    pid = project_id_for(change.name, set(discover()) | folders)
                    workspace = Workspace(root.parent / pid, pid, owner, members)
                    with lock:
                        projects[pid] = workspace
                    return self.json(201, workspace.save_details(actor, change))
            match = ROUTE.fullmatch(self.path)
            if match is None:
                raise WorkspaceError(404, "Project route not found.")
            pid, path = match[1], match[2] or ""
            workspace = open_project(pid)
            workspace.require_member(actor)
            if self.command == "GET" and path in ("", "/"):
                documents = [light(d) for d in workspace.documents(actor)]
                graph = workspace.project_graph(actor)
                provenance = {
                    **workspace.provenance(),
                    "provider": setting("DHF_PROVIDER", "mock"),
                    "artifacts": len(graph["artifacts"]),
                    "synthetic": bool(graph["artifacts"])
                    and all(a["attributes"].get("synthetic") for a in graph["artifacts"]),
                }
                return self.json(
                    200,
                    {
                        "details": workspace.details(),
                        "documents": documents,
                        "provenance": provenance,
                    },
                )
            if self.command == "GET" and path in ("/dashboard", "/traceability", "/review"):
                return self.json(200, self.view(workspace, actor, path[1:]))
            if self.command == "GET" and path == "/settings":
                with workspace.database() as db:
                    rows = workspace.connections(db)
                return self.json(
                    200,
                    {
                        "ai": ai_settings(),
                        "encryption_configured": bool(setting("APP_ENCRYPTION_KEY")),
                        "connections": [workspace.public_connection(row) for row in rows],
                        "audit": workspace.state(actor, "sad")["audit"],
                    },
                )
            if self.command == "GET" and path == "/rtm.csv":
                trace = workspace.insights(actor)["trace"]
                out = io.StringIO()
                writer = csv.writer(out, lineterminator="\n")
                levels = ("architecture", "design", "code", "verification", "risk")
                heads = [level.title() for level in levels]
                writer.writerow(["Requirement", "Title", "Revision", *heads, "Latest results"])
                for row in trace["rows"]:
                    results = " ".join(f"{r['test']}={r['outcome']}" for r in row["results"])
                    cells = [" ".join(row[k]) for k in levels]
                    values = [row["id"], row["title"], row["revision"], *cells, results]
                    writer.writerow([cell_text(value) for value in values])
                name = f"{pid}-rtm.csv"
                return self.reply(
                    200,
                    out.getvalue().encode("utf-8-sig"),
                    "text/csv; charset=utf-8",
                    {"Content-Disposition": f'attachment; filename="{name}"'},
                )
            if self.command == "GET" and path == "/evidence":
                graph = workspace.project_graph(actor)
                if not graph["artifacts"]:
                    raise WorkspaceError(404, "Fetch requirements or upload files first.")
                manifests = [
                    m for d in workspace.documents(actor) if (m := workspace.manifest(d["type"]))
                ]
                name = workspace.details().get("name") or pid
                page_html = create_explorer(graph, manifests, workspace_name=name)
                return self.reply(200, page_html.encode(), "text/html; charset=utf-8")
            if self.command == "POST" and path == "/details":
                change = ProjectInput.model_validate(self.json_body())
                return self.json(200, workspace.save_details(actor, change))
            if self.command == "POST" and path == "/archive":
                archived = self.json_body().get("archived")
                if not isinstance(archived, bool):
                    raise WorkspaceError(400, "Choose archive or restore.")
                return self.json(200, workspace.set_archived(actor, archived))
            if path == "/azure-connections" and self.command == "POST":
                connection = ConnectionInput.model_validate(self.json_body())
                return self.json(200, workspace.save_connection(actor, connection))
            connection = re.fullmatch(rf"/azure-connections/({CID})/(test|fetch|pat)", path)
            if connection:
                cid, action = connection.groups()
                if action == "pat" and self.command == "DELETE":
                    return self.json(200, workspace.remove_pat(actor, cid))
                if action in {"test", "fetch"} and self.command == "POST":
                    doc = self.json_body().get("document_type")
                    if doc is not None and not isinstance(doc, str):
                        raise WorkspaceError(400, "Choose a document type.")
                    return self.json(
                        201 if action == "fetch" else 200,
                        workspace.fetch_or_test(actor, cid, doc, fetch=action == "fetch"),
                    )
            document = re.fullmatch(r"/documents/([a-z]+)/(\w+)(?:/([\w.-]+))?", path)
            if document:
                return self.document_route(pid, workspace, actor, *document.groups())
            raise WorkspaceError(404, "Project route not found.")

        def view(self, workspace: Workspace, actor: str, name: str) -> dict:
            if name == "review":
                return review_items(workspace.documents(actor, with_evidence=True))
            documents = workspace.documents(actor)
            insight = workspace.insights(actor)
            if name == "traceability":
                return {"trace": insight["trace"], "groups": insight["groups"]}
            view = dashboard(insight["trace"], insight["groups"], documents, insight["graph"])
            work = review_items(documents)
            release = workspace.details().get("release") or ""
            return {
                **view,
                "results": results_summary(insight["graph"], release) if release else None,
                "review": {
                    "suggestions": sum(s["status"] == "open" for s in work["suggestions"]),
                    "sections": len(work["sections"]),
                    "rejections": sum(r["status"] == "open" for r in work["rejections"]),
                    "stale": sum(
                        len(d["draft"]["changed_sections"]) for d in documents if d["draft"]
                    ),
                },
            }

        def document_route(
            self,
            pid: str,
            workspace: Workspace,
            actor: str,
            doc: str,
            action: str,
            target: str | None,
        ) -> None:
            if self.command == "GET" and target is None:
                if action == "inputs":
                    return self.json(200, workspace.state(actor, doc))
                if action == "evidence":
                    graph = workspace.graph(actor, doc)
                    if not graph["artifacts"]:
                        raise WorkspaceError(
                            404, "Fetch requirements or upload files to review evidence."
                        )
                    page_html = create_explorer(graph, [], workspace_name=pid)
                    return self.reply(200, page_html.encode(), "text/html; charset=utf-8")
                if action == "changes":
                    return self.json(200, workspace.changes(actor, doc))
                if action == "draft":
                    with lock:
                        job = dict(jobs.get((pid, doc)) or {})
                    return self.json(200, {"job": job, "draft": workspace.draft_state(actor, doc)})
            if self.command == "GET" and action == "files" and target:
                state = workspace.draft_state(actor, doc)
                suffix = Path(target).suffix
                if state is None or target not in (doc + ".docx", doc + ".md"):
                    raise WorkspaceError(404, "Generate a draft first.")
                body = (workspace.drafts_dir(doc) / target).read_bytes()
                filename = f"{pid}-{doc}-v{state['version']}{suffix}"
                return self.reply(
                    200,
                    body,
                    DOWNLOADS[suffix],
                    {"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            if self.command == "POST":
                if action == "source" and target is None:
                    mode = self.json_body().get("mode")
                    if mode not in ("default", "override", "none"):
                        raise WorkspaceError(400, "Choose a requirements source.")
                    workspace.set_source(actor, doc, mode)
                    return self.json(200, {"source": mode})
                if action == "uploads" and target:
                    name = unquote(self.headers.get("X-Input-Filename", ""))
                    raw = self.read_body("application/octet-stream", MAX_FILE_BYTES)
                    return self.json(201, workspace.upload(actor, doc, target, name, raw))
                if action == "snapshot" and target is None:
                    return self.json(201, workspace.save_evidence(actor, doc))
                if action == "draft" and target is None:
                    fresh = self.json_body().get("fresh", False)
                    if not isinstance(fresh, bool):
                        raise WorkspaceError(400, "Choose update or redraft.")
                    return self.json(202, {"job": start_draft(pid, workspace, actor, doc, fresh)})
                if action == "review" and target is None:
                    return self.json(200, workspace.review(actor, doc, self.json_body()))
                if action == "approval" and target is None:
                    body = self.json_body()
                    reference, comment = body.get("reference"), body.get("comment", "")
                    if not isinstance(reference, str) or not isinstance(comment, str):
                        raise WorkspaceError(400, "Enter the eQMS approval reference.")
                    return self.json(201, workspace.approve(actor, doc, reference, comment))
            if self.command == "DELETE" and action == "uploads" and target:
                workspace.delete_upload(actor, doc, target)
                return self.json(200, {})
            raise WorkspaceError(404, "Document route not found.")

    server = LocalServer(("127.0.0.1", port), Handler)
    host, port = server.server_address
    links = {
        actor: f"http://{host}:{port}/#access={quote(grant)}" for grant, actor in grants.items()
    }
    return server, links
