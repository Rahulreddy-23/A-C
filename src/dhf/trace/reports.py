"""Shared deterministic Markdown for CLI reports and local audit exports."""

from collections import Counter
from pathlib import Path

import yaml


def gaps_markdown(findings: list[dict], rules: list[dict]) -> str:
    counts = Counter(f["rule"] for f in findings)
    text = (
        "# Evidence gaps\n\n| Rule | Count | Why it matters | Recommended action |\n"
        "|---|---:|---|---|\n"
    )
    text += "".join(
        f"| {r['id']} | {counts[r['id']]} | {r['title']} | {r['action']} |\n" for r in rules
    )
    text += "\n| Rule | Artifact revision | Finding | Recommended action |\n|---|---|---|---|\n"
    return text + "".join(
        f"| {f['rule']} | [{f['artifact_id']}@r{f['revision']}]({f['source_url']}) | "
        f"{f['message']} | {f['action']} |\n"
        for f in findings
    )


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
