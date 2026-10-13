import csv
import hashlib
import io
import json

from typer.testing import CliRunner

from dhf.cli import app
from dhf.graph import Store
from dhf.graph.export import snapshot_files
from dhf.ingest.fixtures import ingest_fixtures


def test_snapshot_export_is_complete_deterministic_and_locally_hashed(tmp_path):
    graph = ingest_fixtures()
    files = snapshot_files(graph)
    assert files == snapshot_files(
        {"artifacts": graph["artifacts"][::-1], "links": graph["links"][::-1]}
    )
    assert json.loads(files["graph.json"])["artifacts"] == sorted(
        graph["artifacts"], key=lambda a: a["id"]
    )
    rows = list(csv.DictReader(io.StringIO(files["artifacts.csv"])))
    links = list(csv.DictReader(io.StringIO(files["links.csv"])))
    assert len(rows) == 248 and len(links) == 413
    assert rows[0]["content_hash"] and rows[0]["retrieved_at"]
    index = json.loads(files["index.json"])
    assert index["artifacts"] == 248 and index["links"] == 413
    assert all(
        hashlib.sha256(files[name].encode()).hexdigest() == digest
        for name, digest in index["files"].items()
    )
    db = tmp_path / "evidence.sqlite"
    store = Store(db)
    store.ingest(graph)
    store.close()
    out = tmp_path / "export"
    result = CliRunner().invoke(app, ["export-snapshot", "--db", str(db), "--output-dir", str(out)])
    assert result.exit_code == 0 and "248 artifacts, 413 links" in result.output
    assert {p.name: p.read_text() for p in out.iterdir()} == files
