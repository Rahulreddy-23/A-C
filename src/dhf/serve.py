"""Serve the selected explorer and its refresh action on loopback only."""

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dhf.refresh import EmptyRefresh, workspace_page
from dhf.refresh import refresh as run_refresh

# The standalone explorer keeps its stricter CSP and has no network script.
REFRESH_SCRIPT = """<script>
(()=>{const button=document.getElementById('refresh');
const notice=document.getElementById('refresh-status');
button.hidden=false;button.addEventListener('click',async()=>{button.disabled=true;
button.textContent='Reading ADO…';notice.hidden=false;notice.textContent='Reading Azure DevOps…';
try{const response=await fetch('/api/refresh',{method:'POST'}),result=await response.json();
if(!response.ok)throw Error(result.error||'Refresh failed');location.reload()}
catch(error){notice.textContent=String(error.message||error);button.disabled=false;
button.textContent='Refresh from ADO'}})})();
</script>
"""

EMPTY_PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DHF workspace</title><main><h1>DHF workspace</h1>
<p>Read Azure DevOps to create the first evidence snapshot.</p>
<button type="button" id="refresh" hidden>Refresh from ADO</button>
<p id="refresh-status" role="status" hidden></p></main></body></html>
"""

PAGE_POLICY = (
    "frame-ancestors 'none'; default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src data:; connect-src 'self'; "
    "base-uri 'none'; form-action 'none'"
)


class LoopbackHandler(BaseHTTPRequestHandler):
    def allowed(self) -> set[str]:
        bound = self.server.server_address[1]
        return {f"127.0.0.1:{bound}", f"localhost:{bound}"}

    def reply(
        self, status: int, body: bytes, kind: str, headers: dict[str, str] | None = None
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", PAGE_POLICY)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def json(self, status: int, payload: dict) -> None:
        self.reply(status, json.dumps(payload).encode(), "application/json")

    def log_message(self, *args: object) -> None:
        pass


def make_server(
    db: Path,
    documents: Path,
    output_dir: Path,
    port: int = 8765,
    refresh: Callable[..., dict] = run_refresh,
) -> ThreadingHTTPServer:
    lock = threading.Lock()

    class Handler(LoopbackHandler):
        def do_GET(self) -> None:
            if self.headers.get("Host") not in self.allowed():
                return self.json(403, {"error": "Unexpected host"})
            if self.path not in ("/", "/index.html"):
                return self.json(404, {"error": "Not found"})
            try:
                page = workspace_page(db, documents) or EMPTY_PAGE
            except Exception:
                return self.json(500, {"error": "Could not read the local evidence or drafts."})
            html = page.replace("connect-src 'none'", "connect-src 'self'", 1).replace(
                "</body>", REFRESH_SCRIPT + "</body>", 1
            )
            self.reply(200, html.encode(), "text/html; charset=utf-8")

        def do_POST(self) -> None:
            if self.path != "/api/refresh":
                return self.json(404, {"error": "Not found"})
            host = self.headers.get("Host")
            if host not in self.allowed() or self.headers.get("Origin") != f"http://{host}":
                return self.json(403, {"error": "Refresh must come from this workspace page"})
            if not lock.acquire(blocking=False):
                return self.json(409, {"error": "A refresh is already running"})
            try:
                record = refresh(db, documents, output_dir)
            except EmptyRefresh as exc:
                return self.json(502, {"error": str(exc)})
            except PermissionError:
                return self.json(
                    502, {"error": "Check Azure DevOps access and local file permissions."}
                )
            except Exception:
                return self.json(
                    502, {"error": "Refresh failed. Check the ADO and workspace settings."}
                )
            finally:
                lock.release()
            self.json(200, record)

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
