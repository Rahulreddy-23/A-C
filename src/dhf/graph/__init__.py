"""SQLite persistence around pure JSON graph transformations."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from dhf.llm import canonical
from dhf.models.evidence import validate_graph


def diff_graph(previous: dict, current: dict) -> dict:
    before = {a["id"]: a for a in previous["artifacts"]}
    after = {a["id"]: a for a in current["artifacts"]}
    changed = [
        id
        for id, a in after.items()
        if id in before
        and (a["content_hash"], a["source"]["revision"])
        != (before[id]["content_hash"], before[id]["source"]["revision"])
    ]
    # Link-only changes must also stale the source artifact's consumers.
    old_edges = {(e["src"], e["dst"], e["type"], e["origin"]) for e in previous["links"]}
    new_edges = {(e["src"], e["dst"], e["type"], e["origin"]) for e in current["links"]}
    changed += [e[0] for e in old_edges ^ new_edges if e[0] in before and e[0] in after]
    return {
        "changed": sorted(set(changed)),
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
    }


def configuration_only(before: dict, after: dict) -> bool:
    """Whether two revisions differ only in the link classes their source declares: a scope
    change rather than an evidence change. Impact still re-flags drafts that cite them,
    because assessability, and so gap sections, can change with it."""

    def evidence(a: dict) -> tuple:
        attrs = {k: v for k, v in a["attributes"].items() if k != "link_classes"}
        return a["title"], a["body"], canonical(attrs), a["source"]["revision"]

    return before["attributes"].get("link_classes") != after["attributes"].get(
        "link_classes"
    ) and evidence(before) == evidence(after)


class Store:
    def __init__(self, path: Path = Path("out/evidence.sqlite")) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS snapshots "
            "(id INTEGER PRIMARY KEY, at TEXT NOT NULL, graph TEXT NOT NULL, changes TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS ado_refreshes "
            "(snapshot INTEGER PRIMARY KEY REFERENCES snapshots(id), record TEXT NOT NULL)"
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def graph(self, snapshot: int | None = None) -> dict:
        row = (
            self.db.execute("SELECT graph FROM snapshots WHERE id=?", (snapshot,)).fetchone()
            if snapshot is not None
            else self.db.execute("SELECT graph FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        )
        return json.loads(row[0]) if row else {"artifacts": [], "links": []}

    def ingest(self, graph: dict) -> dict:
        with self.ingest_transaction(graph) as (snapshot, _):
            return snapshot

    @contextmanager
    def ingest_transaction(self, graph: dict) -> Iterator[tuple[dict, dict]]:
        """Compare and insert under one writer lock, with room for related audit records."""
        graph = validate_graph(graph)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            changes = diff_graph(self.graph(), graph)
            cursor = self.db.execute(
                "INSERT INTO snapshots(at,graph,changes) VALUES(?,?,?)",
                (datetime.now(UTC).isoformat(), canonical(graph), canonical(changes)),
            )
            yield (
                {
                    "snapshot": cursor.lastrowid,
                    **changes,
                    "artifacts": len(graph["artifacts"]),
                    "links": len(graph["links"]),
                },
                graph,
            )

    def record_refresh(self, record: dict) -> None:
        self.db.execute(
            "INSERT INTO ado_refreshes(snapshot, record) VALUES(?, ?)",
            (record["snapshot"], canonical(record)),
        )

    def refresh_history(self, limit: int = -1) -> list[dict]:
        rows = self.db.execute(
            "SELECT record FROM ado_refreshes ORDER BY snapshot DESC LIMIT ?", (limit,)
        )
        return [json.loads(row[0]) for row in rows]

    def last_changes(self) -> dict:
        row = self.db.execute("SELECT changes FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else {"changed": [], "added": [], "removed": []}
