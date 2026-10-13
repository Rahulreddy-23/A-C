"""Offline evidence exploration: pure payload/render steps and local orchestration."""

import base64
import json
from pathlib import Path

from dhf.models.evidence import validate_graph
from dhf.trace import confirmed_links, gaps, latest_results


def explorer_payload(graph: dict, findings: list[dict], reports: list[dict]) -> dict:
    graph = validate_graph(graph)
    ids = {a["id"] for a in graph["artifacts"]}
    flags: dict[str, list[str]] = {}
    for finding in findings:
        targets = [finding.get("artifact_id"), finding.get("artifact")]
        targets += finding.get("missing", []) + finding.get("unexpected", [])
        for id in targets:
            if id in ids:
                flags.setdefault(id, []).append(finding["rule"])
    stale = []
    for report in reports:
        for section in report["sections"]:
            if section["status"] == "stale":
                stale.append({"document": report["document"], **section})
    affected = {c["artifact"] for s in stale for c in s["causes"] if c.get("artifact")}
    latest = {a["id"] for a in latest_results(graph)}
    return {
        "nodes": [
            {
                "id": a["id"],
                "type": a["type"],
                "title": a["title"],
                "source": a["source"],
                "rules": sorted(set(flags.get(a["id"], []))),
                "stale": a["id"] in affected,
                "latest": a["id"] in latest,
                "outcome": a["attributes"].get("outcome"),
            }
            for a in graph["artifacts"]
        ],
        "links": confirmed_links(graph),
        "findings": findings,
        "stale_sections": stale,
        "notice": "Evidence index; missing links and stale drafts require human review.",
    }


def render_explorer(payload: dict, template: str) -> str:
    """Encode untrusted source strings as inert data, never markup or script."""
    data = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
    return template.replace("__EVIDENCE_BASE64__", data)


def create_explorer(graph: dict, documents: list[dict], reports: list[dict] | None = None) -> str:
    from dhf.graph.reviews import risk_gaps
    from dhf.impact import impact
    from dhf.trace.consistency import consistency

    findings = gaps(graph) + consistency(graph, documents) + risk_gaps(graph)
    reports = reports if reports is not None else [impact(graph, d) for d in documents]
    return render_explorer(
        explorer_payload(graph, findings, reports), Path("specs/render/explorer.html").read_text()
    )
