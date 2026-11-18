"""One refresh: read ADO into a new snapshot, find what changed and what went stale, record it.

A refresh never regenerates documents: it reports stale sections, and regeneration stays
a human decision (`dhf regenerate --stale`). Every refresh appends one line to the log.
"""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

LOG = "refresh_log.jsonl"


def read_ado() -> dict:
    from dhf.ingest.ado import ADO

    ado = ADO()
    try:
        return ado.ingest()
    finally:
        ado.close()


def read_log(output_dir: Path, limit: int = 10) -> list[dict]:
    """Newest first."""
    path = output_dir / LOG
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in reversed(lines[-limit:])]


def refresh(
    db: Path, documents: Path, output_dir: Path, read: Callable[[], dict] = read_ado
) -> dict:
    from dhf.graph import Store
    from dhf.impact import impact
    from dhf.render.explorer import create_explorer
    from dhf.trace import gaps

    started = time.monotonic()
    graph = read()
    store = Store(db)
    try:
        delta = store.ingest(graph)
        current = store.graph()
    finally:
        store.close()
    manifests = [
        json.loads(p.read_text(encoding="utf-8")) for p in sorted(documents.glob("*.manifest.json"))
    ]
    reports = [impact(current, manifest) for manifest in manifests]
    record = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "snapshot": delta["snapshot"],
        "artifacts": delta["artifacts"],
        "links": delta["links"],
        "changed": delta["changed"],
        "added": delta["added"],
        "removed": delta["removed"],
        "findings": len(gaps(current)),
        "stale_sections": sum(
            s["status"] == "stale" for report in reports for s in report["sections"]
        ),
        "seconds": round(time.monotonic() - started, 1),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / LOG).open("a", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps(record, sort_keys=True) + "\n")
    (output_dir / "explorer.html").write_text(
        create_explorer(current, manifests, reports, refreshes=read_log(output_dir)),
        encoding="utf-8",
        newline="\n",
    )
    return record
