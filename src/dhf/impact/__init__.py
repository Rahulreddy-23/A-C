"""Pure section impact and selective regeneration, with explicit evidence causes."""

import copy
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from dhf.generate import (
    assemble,
    expand_sections,
    generate_section,
    load_spec,
    manifest_template,
    sha,
    template_digest,
)
from dhf.graph.queries import query
from dhf.llm import LLM, canonical
from dhf.models.values import ID_PATTERN
from dhf.trace import confirmed_links


def impact(graph: dict, manifest: dict, previous: dict | None = None) -> dict:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    before = {a["artifact_id"]: a for a in manifest["source_snapshot"]}
    changed = {
        id
        for id in before.keys() | nodes.keys()
        if id not in before
        or id not in nodes
        or (before[id]["revision"], before[id]["content_hash"])
        != (nodes[id]["source"]["revision"], nodes[id]["content_hash"])
    }
    if previous is not None:
        from dhf.graph import diff_graph

        delta = diff_graph(previous, graph)
        changed = set(delta["changed"] + delta["added"] + delta["removed"])
    neighbors = {}
    for e in confirmed_links(graph):
        for source, target in ((e["src"], e["dst"]), (e["dst"], e["src"])):
            if source in changed:
                neighbors.setdefault(target, set()).add(source)
    specs = {
        s["id"]: s
        for s in expand_sections(load_spec(manifest["doc_id"], manifest_template(manifest)), graph)
    }
    sections = []
    for section in manifest["sections"]:
        if section["mode"] == "human":
            continue
        cited = set(section["cited_revisions"])
        causes = [
            {"artifact": id, "reason": "cited_revision_changed"} for id in sorted(cited & changed)
        ]
        definition = specs.get(section["id"])
        if definition:
            pack = query(
                graph,
                section["query"],
                {
                    **manifest["params"],
                    **definition.get("query_params", {}),
                    **({"entity": section["entity"]} if section.get("entity") else {}),
                },
            )

            def facts(f: dict) -> dict:
                return {k: v for k, v in f.items() if k != "source_numbers"}

            # Added results and membership changes matter even when no old citation names them.
            prior_facts = section["facts"]
            if previous is not None:
                prior_facts = query(
                    previous,
                    section["query"],
                    {
                        **manifest["params"],
                        **definition.get("query_params", {}),
                        **({"entity": section["entity"]} if section.get("entity") else {}),
                    },
                )["facts"]
            if facts(pack["facts"]) != facts(prior_facts):
                evidence = {a["id"] for a in pack["evidence"]}
                evidence.update(ID_PATTERN.findall(canonical(pack["facts"])))
                dependencies = set().union(*(neighbors.get(id, set()) for id in evidence))
                causal = changed & (evidence | cited)
                if not causal:
                    causal = changed & dependencies
                causes += [
                    {"artifact": id, "reason": "query_facts_changed"}
                    for id in sorted(causal)
                    if id not in cited & changed
                ]
                if not causes:
                    causes = [{"artifact": None, "reason": "query_facts_changed"}]
        else:
            causes.append({"artifact": section.get("entity"), "reason": "entity_removed"})
        possible = [
            {"artifact": source, "via": id, "reason": "one_hop_neighbor"}
            for id in sorted(cited & neighbors.keys())
            for source in sorted(neighbors[id])
        ]
        if causes or possible:
            sections.append(
                {
                    "id": section["id"],
                    "status": "stale" if causes else "possibly_affected",
                    "causes": causes or possible,
                }
            )
    for id in sorted(specs.keys() - {s["id"] for s in manifest["sections"]}):
        sections.append(
            {
                "id": id,
                "status": "stale",
                "causes": [{"artifact": specs[id].get("entity"), "reason": "new_section"}],
            }
        )
    return {
        "document": manifest["doc_id"],
        "changed_artifacts": sorted(changed),
        "sections": sections,
    }


def read_sections(markdown: str) -> dict[str, str]:
    return {
        m[1]: m[0]
        for m in re.finditer(
            r"<!-- section:([^\n]+) -->\n.*?<!-- endsection:\1 -->\n", markdown, re.S
        )
    }


def regenerate(
    graph: dict, manifest: dict, markdown: str, report: dict, out: Path, llm: LLM | None = None
) -> dict:
    llm = llm or LLM(manifest["model"]["provider"])
    start, cost, hits, calls = time.monotonic(), llm.run_spend, llm.hits, llm.calls
    stale = {s["id"] for s in report["sections"] if s["status"] == "stale"}
    old = {s["id"]: s for s in manifest["sections"]}
    actual = read_sections(markdown)
    if set(old) - actual.keys():
        raise ValueError("Missing section boundaries; repair edited Markdown before regeneration")
    sections = []
    for definition in expand_sections(
        load_spec(manifest["doc_id"], manifest_template(manifest)), graph
    ):
        id = definition["id"]
        if id in stale or id not in old:
            sections.append(generate_section(definition, graph, manifest["params"], llm))
        else:
            reused = copy.deepcopy(old[id])
            reused.setdefault("model", {**manifest["model"], "tier": "default"})
            reused["markdown"], reused["sha256"] = actual[id], sha(actual[id])
            sections.append(reused)
    context = {
        **manifest,
        "doc_version": manifest["doc_version"] + 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "template": manifest_template(manifest),
        "template_sha256": template_digest(manifest_template(manifest)),
        "llm_cost_usd": 0 if llm.provider == "copilotstudio" else llm.run_spend - cost,
        **({"copilot_credits": llm.run_spend - cost} if llm.provider == "copilotstudio" else {}),
        "telemetry": {
            "seconds": time.monotonic() - start,
            "cache_hits": llm.hits - hits,
            "calls": llm.calls - calls,
        },
    }
    result = assemble(
        load_spec(manifest["doc_id"], manifest_template(manifest)),
        graph,
        manifest["params"],
        sections,
        context,
    )
    result["manifest"]["impact"] = report
    result["manifest"]["changed_sections"] = sorted(stale)
    from dhf.render import render_docx

    out.mkdir(parents=True, exist_ok=True)
    doc = manifest["doc_id"]
    import hashlib

    from dhf.render.diagram import write_diagrams

    result["manifest"]["diagrams"] = write_diagrams(doc, sections, out)
    result["manifest"]["docx"] = render_docx(
        result["markdown"], out / (doc + ".docx"), markdown, context["generated_at"]
    )
    result["manifest"]["docx"]["sha256"] = hashlib.sha256(
        (out / (doc + ".docx")).read_bytes()
    ).hexdigest()
    (out / (doc + ".md")).write_text(result["markdown"])
    (out / (doc + ".manifest.json")).write_text(json.dumps(result["manifest"], indent=2))
    return result


def write_report(reports: list[dict], root: Path = Path("out")) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "impact.json").write_text(json.dumps(reports, indent=2))
    text = (
        "# Change impact\n\n| Document | Stale | Possibly affected sections | "
        "Optional unit groups |\n|---|---:|---:|---:|\n"
    )
    for report in reports:
        possible = [s for s in report["sections"] if s["status"] == "possibly_affected"]
        groups = {s["id"].split(".UNIT-", 1)[1] for s in possible if ".UNIT-" in s["id"]}
        count = sum(s["status"] == "stale" for s in report["sections"])
        text += f"| {report['document']} | {count} | {len(possible)} | {len(groups)} |\n"
    text += (
        "\nPossibly affected units are optional review groups; "
        "they do not block readiness.\n\n"
        "| Document | Section or unit group | Status | Evidence cause |\n|---|---|---|---|\n"
    )
    for report in reports:
        grouped = {}
        for item in report["sections"]:
            if item["status"] == "possibly_affected" and ".UNIT-" in item["id"]:
                grouped.setdefault("UNIT-" + item["id"].split(".UNIT-", 1)[1], []).append(item)
        for unit, items in sorted(grouped.items()):
            text += (
                f"| {report['document']} | {unit} ({len(items)} subsections) | "
                "possibly affected — optional | "
                + ", ".join(
                    sorted({c["artifact"] for s in items for c in s["causes"] if c["artifact"]})
                )
                + " |\n"
            )
        for section in report["sections"]:
            if section["status"] == "possibly_affected" and ".UNIT-" in section["id"]:
                continue
            causes = "; ".join(
                f"{c['artifact'] or 'query facts'}: {c['reason']}"
                + (f" via {c['via']}" if "via" in c else "")
                for c in section["causes"]
            )
            text += f"| {report['document']} | {section['id']} | {section['status']} | {causes} |\n"
    (root / "impact.md").write_text(text)
