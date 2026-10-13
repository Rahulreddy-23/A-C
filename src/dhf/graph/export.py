"""Pure, deterministic canonical snapshot interchange for reviewed tenant imports."""

import csv
import hashlib
import io
import json

from dhf.llm import canonical
from dhf.models.evidence import validate_graph


def snapshot_files(graph: dict) -> dict[str, str]:
    """Return JSON/CSV payloads; callers decide whether/where to publish them."""
    graph = validate_graph(graph)
    json_text = canonical(graph) + "\n"
    artifact_fields = (
        "id",
        "type",
        "title",
        "body",
        "attributes_json",
        "source_system",
        "source_url",
        "source_native_id",
        "source_revision",
        "retrieved_at",
        "content_hash",
    )
    artifacts = []
    for artifact in graph["artifacts"]:
        source = artifact["source"]
        artifacts.append(
            {
                "id": artifact["id"],
                "type": artifact["type"],
                "title": artifact["title"],
                "body": artifact["body"],
                "attributes_json": canonical(artifact["attributes"]),
                "source_system": source["system"],
                "source_url": source["url"],
                "source_native_id": source["native_id"],
                "source_revision": source["revision"],
                "retrieved_at": source["retrieved_at"],
                "content_hash": artifact["content_hash"],
            }
        )
    link_fields = ("src", "dst", "type", "origin", "confidence", "evidence")
    links = [
        {k: "" if link.get(k) is None else link[k] for k in link_fields} for link in graph["links"]
    ]
    files = {
        "graph.json": json_text,
        "artifacts.csv": _csv(artifact_fields, artifacts),
        "links.csv": _csv(link_fields, links),
    }
    files["index.json"] = (
        json.dumps(
            {
                "format": "dhf.snapshot.v1",
                "artifacts": len(artifacts),
                "links": len(links),
                "files": {
                    name: hashlib.sha256(content.encode()).hexdigest()
                    for name, content in files.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    return files


def _csv(fields: tuple[str, ...], rows: list[dict]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()
