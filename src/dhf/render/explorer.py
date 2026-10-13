"""Offline evidence exploration: pure payload/render steps and local orchestration."""

import base64
import json
from pathlib import Path

from dhf.models.evidence import validate_graph
from dhf.trace import confirmed_links, coverage, gaps, latest_results


def trace_chain(graph: dict, selected: str) -> list[str]:
    """Follow the selected requirement's actual upstream/downstream typed traces."""
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    latest = {a["id"] for a in latest_results(graph)}
    if selected not in nodes:
        return []
    reqs = {selected} if nodes[selected]["type"] == "software_req" else set()
    frontier, visited = {selected}, set()
    # Find requirements from a selected test/unit/change/risk/need without walking
    # sideways from one requirement into its siblings.
    while frontier:
        current = frontier.pop()
        if current in visited:
            continue
        visited.add(current)
        if nodes[current]["type"] == "software_req":
            reqs.add(current)
            continue
        for edge in edges:
            peer = (
                edge["dst"]
                if edge["src"] == current
                else edge["src"]
                if edge["dst"] == current
                else None
            )
            if (
                peer
                and peer not in visited
                and (
                    nodes[peer]["type"] == "software_req"
                    or nodes[current]["type"]
                    in ("user_need", "system_req", "risk_control", "hazard", "test_result")
                    and nodes[peer]["type"] in ("system_req", "risk_control", "test_case")
                )
            ):
                frontier.add(peer)
    result = {selected} | reqs
    for req in reqs:
        for edge in edges:
            if edge["src"] == req and edge["type"] in (
                "derives_from",
                "allocated_to",
                "implements",
            ):
                result.add(edge["dst"])
            elif edge["dst"] == req and edge["type"] in ("verifies", "implements"):
                result.add(edge["src"])
    for id in list(result):
        if nodes[id]["type"] == "test_case":
            result.update(
                e["src"]
                for e in edges
                if e["dst"] == id and e["type"] == "executes" and e["src"] in latest
            )
        elif nodes[id]["type"] == "software_unit":
            component = nodes[id]["attributes"].get("component")
            if component in nodes:
                result.add(component)
    for id in list(result):
        result.update(
            e["dst"]
            for e in edges
            if e["src"] == id
            and (
                nodes[id]["type"] == "risk_control"
                and e["type"] == "mitigates"
                or nodes[id]["type"] == "system_req"
                and e["type"] == "derives_from"
            )
        )
    return sorted(result)


def explorer_payload(
    graph: dict,
    findings: list[dict],
    reports: list[dict],
    documents: list[dict] | None = None,
    presentation: dict | None = None,
) -> dict:
    """Pure JSON payload step; file-backed presentation metadata is an input."""
    from collections import Counter

    from dhf.graph.reviews import risk_rows

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
    documents = documents or []
    release = next(
        (str(d["params"]["release"]) for d in documents if d.get("params", {}).get("release")),
        "1.1",
    )
    presentation = presentation or {}
    rules = presentation.get("rules", [])
    titles = presentation.get("document_titles", {})
    document_rows = []
    for document in documents:
        title = titles.get(document["doc_id"])
        document_rows.append(
            {
                "id": document["doc_id"],
                "title": title or document["doc_id"].upper(),
                "version": document.get("doc_version"),
                "generated_at": document.get("generated_at"),
                "model": document.get("model", {}),
                "validation": document.get("validation", {}),
                "sections": [
                    {
                        key: section.get(key)
                        for key in (
                            "id",
                            "title",
                            "mode",
                            "status",
                            "claims",
                            "cited_revisions",
                            "markdown",
                        )
                    }
                    for section in document["sections"]
                ],
            }
        )
    return {
        "release": release,
        "coverage": coverage(graph, release),
        "verification": dict(
            Counter(
                a["attributes"].get("outcome", "Unknown") for a in latest_results(graph, release)
            )
        ),
        "rules": [{k: r.get(k, "") for k in ("id", "title", "action")} for r in rules],
        "documents": document_rows,
        "impact_reports": reports,
        "risk": risk_rows(graph),
        "nodes": [
            {
                "id": a["id"],
                "type": a["type"],
                "title": a["title"],
                "source": a["source"],
                "body_excerpt": a["body"][:1600],
                "content_hash": a["content_hash"],
                "rules": sorted(set(flags.get(a["id"], []))),
                "stale": a["id"] in affected,
                "latest": a["id"] in latest,
                "outcome": a["attributes"].get("outcome"),
            }
            for a in graph["artifacts"]
        ],
        "chains": {a["id"]: trace_chain(graph, a["id"]) for a in graph["artifacts"]},
        "links": confirmed_links(graph),
        "findings": findings,
        "stale_sections": stale,
        "notice": "Read-only evidence snapshot; human review required.",
    }


def render_explorer(payload: dict, template: str) -> str:
    """Encode untrusted source strings as inert data, never markup or script."""
    data = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
    return template.replace("__EVIDENCE_BASE64__", data)


def create_explorer(
    graph: dict,
    documents: list[dict],
    reports: list[dict] | None = None,
    baselines: list[dict] | None = None,
) -> str:
    import yaml

    from dhf.graph.reviews import risk_gaps
    from dhf.impact import impact
    from dhf.trace.consistency import consistency

    findings = gaps(graph) + consistency(graph, documents) + risk_gaps(graph)
    findings += [{**f, "scope": "baseline"} for f in consistency(graph, baselines or [])]
    reports = reports if reports is not None else [impact(graph, d) for d in documents]
    presentation = {
        "rules": [
            rule
            for path in sorted(Path("specs/rules").glob("*.yaml"))
            for rule in yaml.safe_load(path.read_text()).get("rules", [])
        ],
        "document_titles": {
            path.stem: yaml.safe_load(path.read_text()).get("title")
            for path in sorted(Path("specs/documents").glob("*.yaml"))
        },
    }
    return render_explorer(
        explorer_payload(graph, findings, reports, documents, presentation),
        Path("specs/render/explorer.html").read_text(),
    )
