"""Pure project views for the browser: dashboard, requirement trace, gap groups, review items.

Every count and percentage is computed here from the evidence graph and draft manifests; the
page only renders it, so the browser never derives a regulated number (AGENTS rule 1)."""

from collections import Counter
from pathlib import Path

import yaml

from dhf.models.evidence import validate_graph
from dhf.review import claim_key
from dhf.trace import can_carry, confirmed_links, latest_results

REQUIREMENT_TYPES = ("user_need", "system_req", "software_req")
# Category → (label, link, direction, peer types). "out" links start at the requirement.
TRACE = {
    "architecture": ("Architecture (SAD)", "allocated_to", "out", ("component",)),
    "design": ("Design (SDD)", "implements", "in", ("software_unit",)),
    "code": ("Code", "implements", "in", ("code_change",)),
    "verification": ("Verification", "verifies", "in", ("test_case",)),
    "risk": ("Risk controls", "implements", "out", ("risk_control",)),
}


def merged_graph(graphs: list[dict]) -> dict:
    """One project graph from the per-document evidence: the latest read of each artifact."""
    artifacts: dict[str, dict] = {}
    for graph in graphs:
        for item in graph["artifacts"]:
            held = artifacts.get(item["id"])
            if held is None or item["source"]["retrieved_at"] >= held["source"]["retrieved_at"]:
                artifacts[item["id"]] = item
    links = {
        (e["src"], e["dst"], e["type"]): e
        for graph in graphs
        for e in graph["links"]
        if e["src"] in artifacts and e["dst"] in artifacts
    }
    return validate_graph({"artifacts": list(artifacts.values()), "links": list(links.values())})


def subjects(graph: dict) -> list[dict]:
    """Software requirements carry the trace, as in the RTM; system ones when none exist."""
    for kind in ("software_req", "system_req"):
        found = sorted((a for a in graph["artifacts"] if a["type"] == kind), key=lambda a: a["id"])
        if found:
            return found
    return []


def requirement_trace(graph: dict) -> dict:
    """Per-requirement trace rows plus coverage for each level, with drill-down IDs."""
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    results = {r["attributes"]["test_case"]: r for r in latest_results(graph)}
    requirements = subjects(graph)
    index: dict[tuple[str, str, str], set[str]] = {}
    for e in edges:  # one pass, so each row reads its peers instead of rescanning every edge
        index.setdefault((e["src"], e["type"], "out"), set()).add(e["dst"])
        index.setdefault((e["dst"], e["type"], "in"), set()).add(e["src"])

    def peers(id: str, link: str, direction: str, types: tuple[str, ...]) -> list[str]:
        found = index.get((id, link, direction), set())
        return sorted(n for n in found if n in nodes and nodes[n]["type"] in types)

    rows = []
    for req in requirements:
        row = {
            "id": req["id"],
            "type": req["type"],
            "title": req["title"],
            "url": req["source"]["url"],
            "revision": req["source"]["revision"],
            **{key: peers(req["id"], *spec[1:]) for key, spec in TRACE.items()},
        }
        row["hazards"] = sorted(
            {h for c in row["risk"] for h in index.get((c, "mitigates", "out"), set())}
        )
        row["results"] = [
            {"test": t, "result": results[t]["id"], "outcome": results[t]["attributes"]["outcome"]}
            for t in row["verification"]
            if t in results
        ]
        rows.append(row)
    coverage = []
    for key, (label, link, _, types) in TRACE.items():
        rule = {"link": link, "peer_types": list(types)}
        covered = sum(bool(row[key]) for row in rows)
        coverage.append(
            {
                "id": key,
                "label": label,
                "covered": covered,
                "total": len(rows),
                "missing": len(rows) - covered,
                "percent": round(covered / len(rows) * 100, 1) if rows else 0.0,
                # Inputs that cannot hold this link (no repository, no test plans) say so.
                "assessable": any(can_carry(r, rule) for r in requirements),
            }
        )
    passed = sum(
        bool(row["results"]) and all(r["outcome"] == "Passed" for r in row["results"])
        for row in rows
    )
    return {
        "subject": requirements[0]["type"] if requirements else "software_req",
        "rows": rows,
        "coverage": coverage,
        "passed": passed,
        "titles": {id: nodes[id]["title"] for row in rows for id in linked_ids(row)},
        "types": {id: nodes[id]["type"] for row in rows for id in linked_ids(row)},
    }


def linked_ids(row: dict) -> list[str]:
    return [id for key in (*TRACE, "hazards") for id in row[key]] + [
        r["result"] for r in row["results"]
    ]


def gap_groups(findings: list[dict], blind: list[str], rules: list[dict]) -> list[dict]:
    """Findings grouped by what is missing, per specs/rules/categories.yaml."""
    categories = yaml.safe_load(Path("specs/rules/categories.yaml").read_text(encoding="utf-8"))[
        "categories"
    ]
    owner = {rule: c["id"] for c in categories for rule in c["rules"]}
    titles = {r["id"]: r.get("title", r["id"]) for r in rules}
    groups = [
        {
            "id": c["id"],
            "label": c["label"],
            "description": c["description"],
            "findings": [f for f in findings if owner.get(f["rule"]) == c["id"]],
            "not_assessable": [
                {"rule": r, "title": titles.get(r, r)} for r in blind if owner.get(r) == c["id"]
            ],
        }
        for c in categories
    ]
    other = [f for f in findings if f["rule"] not in owner]
    if other:
        groups.append(
            {
                "id": "other",
                "label": "Other findings",
                "description": "Findings from rules not yet grouped.",
                "findings": other,
                "not_assessable": [],
            }
        )
    return groups


def blocked_sections(readiness: dict) -> set[str]:
    return {b["section"] for b in readiness["blockers"] if "section" in b}


def dashboard(trace: dict, groups: list[dict], documents: list[dict], graph: dict) -> dict:
    """Headline numbers. Documentation completeness counts sections with no review blocker;
    traceability completeness counts requirements both allocated and verified, over the
    levels these inputs can record (neither recordable: not assessable, never 0%)."""
    counts = Counter(a["type"] for a in graph["artifacts"])
    drafted = [d for d in documents if d.get("draft")]
    total = sum(len(d["draft"]["sections"]) for d in drafted)
    clear = sum(
        len(d["draft"]["sections"]) - len(blocked_sections(d["draft"]["readiness"]))
        for d in drafted
    )
    rows = trace["rows"]
    levels = [c["id"] for c in trace["coverage"] if c["assessable"]]
    levels = [k for k in ("architecture", "verification") if k in levels]
    complete = sum(all(r[k] for k in levels) for r in rows) if levels else 0
    return {
        "requirements": {kind: counts[kind] for kind in REQUIREMENT_TYPES},
        "subject": trace["subject"],
        "coverage": trace["coverage"],
        "documentation": {
            "percent": round(clear / total * 100, 1) if total else 0.0,
            "complete_sections": clear,
            "sections": total,
            "drafted": len(drafted),
            "documents": len(documents),
        },
        "traceability": {
            "percent": round(complete / len(rows) * 100, 1) if rows and levels else None,
            "complete": complete,
            "total": len(rows),
            "levels": levels,
        },
        "gaps": [{"id": g["id"], "label": g["label"], "count": len(g["findings"])} for g in groups],
        "documents": [{k: d[k] for k in ("type", "title", "stage", "future")} for d in documents],
    }


def review_items(documents: list[dict]) -> dict:
    """Suggestions to resolve, sections to author and validator rejections, per document."""
    suggestions, sections, rejections, queue = [], [], [], []
    for d in documents:
        draft = d.get("draft")
        if not draft:
            continue
        resolutions = draft["readiness"]["resolutions"]
        blocked = {
            (b.get("section"), b["reason"])
            for b in draft["readiness"]["blockers"]
            if "section" in b
        }
        evidence = draft["evidence"]
        seen: dict[str, dict] = {}
        for section in draft["sections"]:
            for claim in section["claims"]:
                if claim["kind"] != "suggested":
                    continue
                key = claim_key(claim)
                if key in seen:
                    seen[key]["sections"].append(section["title"])
                    continue
                decision = resolutions.get(key, {})
                seen[key] = {
                    "document": d["type"],
                    "document_title": d["title"],
                    "key": key,
                    "section": section["id"],
                    "sections": [section["title"]],
                    "text": claim["text"],
                    "confidence": claim.get("confidence"),
                    "citations": [evidence.get(id, {"id": id}) for id in claim["citations"]],
                    "status": decision.get("decision", "open"),
                    "reviewer": decision.get("reviewer", ""),
                    "rationale": decision.get("rationale", ""),
                }
            for reason in ("human_input_required", "ai_unavailable"):
                if (section["id"], reason) in blocked:
                    sections.append(
                        {
                            "document": d["type"],
                            "document_title": d["title"],
                            "section": section["id"],
                            "title": section["title"],
                            "reason": reason,
                            "manual": reason == "ai_unavailable",
                        }
                    )
        suggestions.extend(seen.values())
        reviewed = {
            b["event"]
            for b in draft["readiness"]["blockers"]
            if b["reason"] == "unreviewed_validator_rejection"
        }
        for event in draft["validation"]["rejected"]:
            key = claim_key(event)
            rejections.append(
                {
                    "document": d["type"],
                    "document_title": d["title"],
                    "key": key,
                    "section": event.get("section", ""),
                    "reason": event.get("reason", ""),
                    # The validator keeps no rejected text, only what failed.
                    "detail": ", ".join(map(str, event.get("ids") or event.get("numbers") or [])),
                    "status": "open" if key in reviewed else "reviewed",
                }
            )
        queue.append(
            {
                "document": d["type"],
                "document_title": d["title"],
                "stage": d["stage"],
                "version": draft["version"],
                "ready": draft["readiness"]["ready"],
                "blockers": dict(Counter(b["reason"] for b in draft["readiness"]["blockers"])),
                "approvals": d.get("approvals", []),
                "tracked_changes": draft["docx"],
                "redline": draft["redline"],
            }
        )
    return {
        "suggestions": suggestions,
        "sections": sections,
        "rejections": rejections,
        "queue": queue,
    }
