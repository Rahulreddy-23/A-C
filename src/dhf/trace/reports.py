"""Shared deterministic Markdown for CLI reports and local audit exports."""

from collections import Counter
from pathlib import Path

import yaml


def rule_table(
    findings: list[dict], rules: list[dict], blind: list[str] | None = None, label: str = "Finding"
) -> str:
    """One row per rule: count of findings, or 'not assessable' when no source can carry it."""
    counts = Counter(f["rule"] for f in findings)
    text = f"| Rule | Count | {label} | Recommended action |\n|---|---:|---|---|\n"
    return text + "".join(
        f"| {r['id']} | {'not assessable' if r['id'] in (blind or []) else counts[r['id']]} | "
        f"{r['title']} | {r['action']} |\n"
        for r in rules
    )


def gaps_markdown(
    findings: list[dict], rules: list[dict], unassessable: list[str] | None = None
) -> str:
    """Gap table; rules no ingested source can carry are named once as not assessable."""
    text = "# Evidence gaps\n\n" + rule_table(findings, rules, unassessable, "Why it matters")
    if unassessable:
        text += (
            "\nNot assessable: " + ", ".join(sorted(unassessable)) + ". The sources these "
            "artifacts came from cannot hold the required link (for example documents, which "
            "carry no ADO Tested By or Parent links), so absence is not evidence of a gap. "
            "Ingest the system that holds these links to assess them.\n"
        )
    text += "\n| Rule | Artifact revision | Finding | Recommended action |\n|---|---|---|---|\n"
    return text + "".join(
        f"| {f['rule']} | [{f['artifact_id']}@r{f['revision']}]({f['source_url']}) | "
        f"{f['message']} | {f['action']} |\n"
        for f in findings
    )


def import_markdown(
    summary: dict,
    findings: list[dict],
    rules: list[dict],
    graph: dict,
    unassessable: list[str] | None = None,
) -> str:
    """Document-baseline import: what was read, what was skipped, consistency findings."""
    nodes = {a["id"]: a for a in graph["artifacts"]}
    text = "# Document baseline import\n\n## Evidence imported\n\n| Type | Count |\n|---|---:|\n"
    text += "".join(f"| {k} | {v} |\n" for k, v in summary["artifact_counts"].items())
    text += "".join(f"| link: {k} | {v} |\n" for k, v in summary["link_counts"].items())
    text += "\n## Files\n\n" + "".join(f"- imported: {n}\n" for n in summary["imported_files"])
    text += "".join(f"- skipped (older issue): {n}\n" for n in summary.get("older_issues", []))
    text += "".join(f"- excluded (reference or redline): {n}\n" for n in summary["excluded_files"])
    text += "".join(f"- not imported (no extraction rule): {n}\n" for n in summary["unused_files"])
    text += "\n## Import notes\n\n" + "".join(f"- {k}: {v}\n" for k, v in summary["notes"].items())
    text += "".join(f"- duplicate ignored: {d}\n" for d in summary.get("duplicates_ignored", []))
    text += "\n## Consistency findings\n\n" + rule_table(findings, rules, unassessable)
    text += "\n| Rule | Artifact | Document | Detail |\n|---|---|---|---|\n"
    from dhf.ingest.documents import document_of

    for f in findings:
        node = nodes[f["artifact_id"]]
        attrs = node["attributes"]
        detail = "; ".join(
            attrs.get("unresolved_allocations", []) + attrs.get("missing_sections", [])
        )
        text += f"| {f['rule']} | {f['artifact_id']} | {document_of(node)} | {detail} |\n"
    return text


def gap_rules() -> list[dict]:
    return yaml.safe_load(Path("specs/rules/gaps.yaml").read_text())["rules"]


def rtm_markdown(graph: dict, rows: list[dict]) -> str:
    nodes = {a["id"]: a for a in graph["artifacts"]}

    def citation(id: str) -> str:
        return f"[{id}]({nodes[id]['source']['url']})"

    text = (
        "# Requirement trace matrix\n\n"
        "| Requirement | Rev | Components | Units | Changes | Tests | Latest results |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    for row in rows:
        cells = [citation(row["requirement"]), row["revision"]]
        cells += [
            ", ".join(citation(id) for id in row[key])
            for key in ("components", "units", "changes", "tests")
        ]
        cells += [", ".join(citation(v["result"]) + ": " + v["outcome"] for v in row["results"])]
        text += "| " + " | ".join(cells) + " |\n"
    return text
