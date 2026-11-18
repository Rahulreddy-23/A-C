import copy
import http.client
import json
import threading

import pytest
from test_explorer import decode

from dhf.graph import Store
from dhf.ingest.fixtures import ingest_fixtures
from dhf.refresh import EmptyRefresh, refresh
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

    log = [
        json.loads(line)
        for line in (out / "refresh_log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [record["snapshot"] for record in log] == [1, 2]
    assert log[-1] == second
    assert (out / "gaps.md").read_text(encoding="utf-8").startswith("# Evidence gaps")
    assert (
        len(json.loads((out / "gaps.json").read_text(encoding="utf-8"))["findings"])
        == second["findings"]
    )
    payload = decode((out / "explorer.html").read_text(encoding="utf-8"))
    assert payload["refreshes"][0]["changed"] == ["SRS-021"]


def test_served_refresh_accepts_only_its_own_page(tmp_path):
    calls = []

    def fake_refresh(db, documents, output_dir):
        calls.append(db)
        return {"snapshot": 7}

    (tmp_path / "explorer.html").write_text(
        "Unrelated exported workspace", encoding="utf-8", newline="\n"
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
        return response.status, body, dict(response.getheaders())

    try:
        own = {"Host": f"127.0.0.1:{port}"}
        status, page, headers = request("GET", "/", own)
        assert status == 200 and "first evidence snapshot" in page and "/api/refresh" in page
        assert "Unrelated exported workspace" not in page
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert headers["X-Frame-Options"] == "DENY"
        store = Store(tmp_path / "db")
        try:
            store.ingest(ingest_fixtures())
        finally:
            store.close()
        status, page, _ = request("GET", "/", own)
        assert status == 200 and len(decode(page)["nodes"]) == 248
        assert "connect-src 'self'" in page
        assert request("GET", "/", {"Host": "evil.example"})[0] == 403
        assert request("POST", "/api/refresh", own)[0] == 403  # no Origin
        assert request("POST", "/api/refresh", {**own, "Origin": "https://evil.example"})[0] == 403
        assert calls == []
        status, body, _ = request(
            "POST", "/api/refresh", {**own, "Origin": f"http://127.0.0.1:{port}"}
        )
        assert status == 200 and json.loads(body) == {"snapshot": 7} and len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()


def test_empty_read_and_failed_render_keep_last_snapshot(tmp_path, monkeypatch) -> None:
    graph = ingest_fixtures()
    changed = revised(graph, "SRS-021")
    db, out = tmp_path / "evidence.sqlite", tmp_path / "out"
    first = refresh(db, tmp_path / "docs", out, read=lambda: graph)
    assert first["snapshot"] == 1

    with pytest.raises(EmptyRefresh):
        refresh(db, tmp_path / "docs", out, read=lambda: {"artifacts": [], "links": []})

    def broken_render(*args, **kwargs):
        raise ValueError("render failed")

    with monkeypatch.context() as patch:
        patch.setattr("dhf.refresh.create_explorer", broken_render)
        with pytest.raises(ValueError, match="render failed"):
            refresh(db, tmp_path / "docs", out, read=lambda: changed)
    second = refresh(db, tmp_path / "docs", out, read=lambda: changed)
    assert second["snapshot"] == 2
    assert second["changed"] == ["SRS-021"]
