import copy
import http.client
import json
import threading

from test_explorer import decode

from dhf.ingest.fixtures import ingest_fixtures
from dhf.refresh import read_log, refresh
from dhf.serve import make_server


def revised(graph: dict, artifact_id: str) -> dict:
    graph = copy.deepcopy(graph)
    artifact = next(a for a in graph["artifacts"] if a["id"] == artifact_id)
    artifact["source"]["revision"] = str(int(artifact["source"]["revision"]) + 1)
    return graph


def test_refresh_records_changes_and_puts_history_in_the_explorer(tmp_path):
    first = ingest_fixtures()
    reads = iter([first, revised(first, "SRS-021")])
    db, docs, out = tmp_path / "evidence.sqlite", tmp_path / "docs", tmp_path / "out"
    docs.mkdir()

    initial = refresh(db, docs, out, read=lambda: next(reads))
    assert initial["snapshot"] == 1 and len(initial["added"]) == 248
    second = refresh(db, docs, out, read=lambda: next(reads))
    assert second["snapshot"] == 2
    assert second["changed"] == ["SRS-021"] and not second["added"] and not second["removed"]

    log = read_log(out)
    assert [r["snapshot"] for r in log] == [2, 1]  # newest first
    payload = decode((out / "explorer.html").read_text(encoding="utf-8"))
    assert payload["refreshes"][0]["changed"] == ["SRS-021"]


def test_served_refresh_accepts_only_its_own_page(tmp_path):
    calls = []

    def fake_refresh(db, documents, output_dir):
        calls.append(db)
        return {"snapshot": 7}

    (tmp_path / "explorer.html").write_text(
        "<meta content=\"connect-src 'none'\"><body></body>", encoding="utf-8", newline="\n"
    )
    server = make_server(tmp_path / "db", tmp_path, tmp_path, port=0, refresh=fake_refresh)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def request(method, path, headers):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read().decode()
        connection.close()
        return response.status, body

    try:
        own = {"Host": f"127.0.0.1:{port}"}
        status, page = request("GET", "/", own)
        assert status == 200 and "connect-src 'self'" in page and "/api/refresh" in page
        assert request("GET", "/", {"Host": "evil.example"})[0] == 403
        assert request("POST", "/api/refresh", own)[0] == 403  # no Origin
        assert request("POST", "/api/refresh", {**own, "Origin": "https://evil.example"})[0] == 403
        assert calls == []
        status, body = request(
            "POST", "/api/refresh", {**own, "Origin": f"http://127.0.0.1:{port}"}
        )
        assert status == 200 and json.loads(body) == {"snapshot": 7} and len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
