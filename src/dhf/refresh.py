"""Read ADO, record changes and publish local review outputs without redrafting."""

import json
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from dhf.graph import Store
from dhf.impact import impact
from dhf.llm import exclusive
from dhf.render.explorer import create_explorer
from dhf.trace.reports import gap_report

LOG = "refresh_log.jsonl"


class EmptyRefresh(ValueError):
    """An empty read must never supersede a populated snapshot."""


def read_ado() -> dict:
    from dhf.ingest.ado import ADO

    ado = ADO()
    try:
        ado.read_only = True
        return ado.ingest()
    finally:
        ado.close()


def read_manifests(documents: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(documents.glob("*.manifest.json"))
    ]


def workspace_page(db: Path, documents: Path) -> str | None:
    """Render the selected database rather than another snapshot in the output folder."""
    if not db.is_file():
        return None
    store = Store(db)
    try:
        store.db.execute("BEGIN")
        graph = store.graph()
        history = store.refresh_history(limit=10)
    finally:
        store.close()
    if not graph["artifacts"]:
        return None
    return create_explorer(graph, read_manifests(documents), refreshes=history)


def refresh(
    db: Path, documents: Path, output_dir: Path, read: Callable[[], dict] = read_ado
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with (
        exclusive(output_dir / ".refresh.lock"),
        tempfile.TemporaryDirectory(prefix=".refresh-", dir=output_dir) as staging,
    ):
        graph = read()
        if not graph["artifacts"]:
            raise EmptyRefresh("ADO returned no evidence. Check the project, scope and mapping.")
        manifests = read_manifests(documents)
        store = Store(db)
        try:
            with store.ingest_transaction(graph) as (delta, current):
                reports = [impact(current, manifest) for manifest in manifests]
                gap_json, gap_md = gap_report(current)
                record = {
                    "at": datetime.now(UTC).isoformat(timespec="seconds"),
                    **delta,
                    "findings": len(gap_json["findings"]),
                    "stale_sections": sum(
                        section["status"] == "stale"
                        for report in reports
                        for section in report["sections"]
                    ),
                    "seconds": round(time.monotonic() - started, 1),
                }
                store.record_refresh(record)
                history = store.refresh_history()
                outputs = {
                    "explorer.html": create_explorer(
                        current, manifests, reports, refreshes=history[:10]
                    ),
                    "gaps.json": json.dumps(gap_json, indent=2),
                    "gaps.md": gap_md,
                    LOG: "".join(
                        json.dumps(row, sort_keys=True) + "\n" for row in reversed(history)
                    ),
                }
                for name, content in outputs.items():
                    (Path(staging) / name).write_text(content, encoding="utf-8", newline="\n")
        finally:
            store.close()

        # Publish complete files only. If a file is busy, SQLite retains the audit event.
        for name in outputs:
            (Path(staging) / name).replace(output_dir / name)
        return record
