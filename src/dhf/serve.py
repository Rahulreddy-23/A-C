"""Local-only review server: the explorer plus a "Refresh from ADO" action.

Binds to 127.0.0.1 only. Every request must name this server as its Host, and a refresh
must come from this server's own page (Origin), so other websites open in the same
browser cannot trigger ADO reads.
"""

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dhf.refresh import refresh as run_refresh

# The offline explorer contains no network code. Only the served page gets this button
# script, which calls back to this server alone.
REFRESH_SCRIPT = """<script>
(()=>{const button=document.getElementById('refresh'),notice=document.getElementById('notice');
button.hidden=false;button.addEventListener('click',async()=>{button.disabled=true;
button.textContent='Reading ADO\u2026';notice.textContent='Reading Azure DevOps (read-only)\u2026';
try{const response=await fetch('/api/refresh',{method:'POST'}),result=await response.json();
if(!response.ok)throw Error(result.error||'Refresh failed');location.reload()}
catch(error){notice.textContent=String(error.message||error);button.disabled=false;
button.textContent='Refresh from ADO'}})})();
</script>
"""

# Messages from these are written for people and carry no secrets; others report the class.
READABLE = (PermissionError, ValueError, FileNotFoundError)


def make_server(
    db: Path,
    documents: Path,
    output_dir: Path,
    port: int = 8765,
    refresh: Callable[..., dict] = run_refresh,
) -> ThreadingHTTPServer:
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def allowed(self) -> set[str]:
            bound = self.server.server_address[1]
            return {f"127.0.0.1:{bound}", f"localhost:{bound}"}

        def reply(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def json(self, status: int, payload: dict) -> None:
            self.reply(status, json.dumps(payload).encode(), "application/json")

        def do_GET(self) -> None:
            if self.headers.get("Host") not in self.allowed():
                return self.json(403, {"error": "Unexpected host"})
            if self.path not in ("/", "/index.html"):
                return self.json(404, {"error": "Not found"})
            page = output_dir / "explorer.html"
            if not page.exists():
                return self.reply(
                    200,
                    b"<!doctype html><meta charset='utf-8'><title>DHF workspace</title>"
                    b"<p>No explorer yet. Run <code>uv run dhf refresh</code> first.</p>",
                    "text/html; charset=utf-8",
                )
            # The offline file forbids all connections; the served page may call this server.
            html = (
                page.read_text(encoding="utf-8")
                .replace("connect-src 'none'", "connect-src 'self'", 1)
                .replace("</body>", REFRESH_SCRIPT + "</body>", 1)
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
            except READABLE as exc:
                return self.json(502, {"error": f"{type(exc).__name__}: {exc}"})
            except Exception as exc:  # Class only: messages can echo request details.
                return self.json(502, {"error": f"Refresh failed ({type(exc).__name__})"})
            finally:
                lock.release()
            self.json(200, record)

        def log_message(self, *args) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
