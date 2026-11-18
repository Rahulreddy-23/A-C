"""Browser inputs and project API served only on the local loopback interface."""

import json
import re
import secrets
import threading
from http.cookies import CookieError, SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote

from pydantic import ValidationError

from dhf.render.explorer import create_explorer
from dhf.serve import LoopbackHandler
from dhf.workspace import Workspace
from dhf.workspace.sources import ConnectionInput, WorkspaceError
from dhf.workspace.uploads import ALLOWED_TYPES, MAX_FILE_BYTES

ROUTE = re.compile(r"/api/projects/([a-zA-Z0-9_-]{1,64})(/[^?#]*)")
JSON_LIMIT = 96 * 1024
CID = r"[0-9a-f]{32}"


def make_workspace_server(
    root: Path, project_id: str, owner: str, members: list[str], port: int = 8765
) -> tuple[ThreadingHTTPServer, dict[str, str]]:
    workspace = Workspace(root, project_id, owner, members)
    grants = {secrets.token_urlsafe(32): actor for actor in (owner, *members)}
    sessions: dict[str, str] = {}
    lock = threading.Lock()
    cookie_name = "dhf_session_" + secrets.token_hex(8)
    page = Path("specs/render/workspace.html").read_bytes()

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
            except (ValidationError, UnicodeError, json.JSONDecodeError):
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
                    raise WorkspaceError(401, "Open the access link issued for this workspace.")
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
                raise WorkspaceError(401, "Open the access link issued for this workspace.")
            workspace.require_member(actor)
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
                        "profile": workspace.profile,
                        "file_types": sorted(ALLOWED_TYPES),
                    },
                )
            match = ROUTE.fullmatch(self.path)
            if match is None or match[1] != project_id:
                raise WorkspaceError(404, "Project route not found.")
            path = match[2]
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
            document = re.fullmatch(r"/documents/([a-z]+)/(\w+)(?:/([\w-]+))?", path)
            if document:
                return self.document_route(actor, *document.groups())
            raise WorkspaceError(404, "Project route not found.")

        def document_route(self, actor: str, doc: str, action: str, target: str | None) -> None:
            if self.command == "GET" and target is None:
                if action == "inputs":
                    return self.json(200, workspace.state(actor, doc))
                if action == "evidence":
                    graph = workspace.graph(actor, doc)
                    if not graph["artifacts"]:
                        raise WorkspaceError(
                            404, "Fetch requirements or upload files to review evidence."
                        )
                    page = create_explorer(graph, [], workspace_name=project_id)
                    return self.reply(200, page.encode(), "text/html; charset=utf-8")
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
            if self.command == "DELETE" and action == "uploads" and target:
                workspace.delete_upload(actor, doc, target)
                return self.json(200, {})
            raise WorkspaceError(404, "Document route not found.")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    host, port = server.server_address
    links = {
        actor: f"http://{host}:{port}/#access={quote(grant)}" for grant, actor in grants.items()
    }
    return server, links
