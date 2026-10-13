"""AI-assisted review proposals, persisted separately and never written to ADO."""

import json
from pathlib import Path

import yaml

from dhf.generate import generate_section
from dhf.llm import LLM
from dhf.trace import confirmed_links


def proposal_jobs(graph: dict, documents: list[dict]) -> list[dict]:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    jobs = []
    for rule in yaml.safe_load(Path("specs/rules/proposals.yaml").read_text())["rules"]:
        if rule["op"] == "requirement_implementation":
            subjects = [a for a in nodes.values() if a["type"] == "software_req"]
        elif rule["op"] == "orphan_requirement":
            subjects = [
                a
                for a in nodes.values()
                if a["type"] == "software_unit"
                and not any(e["src"] == a["id"] and e["type"] == "implements" for e in edges)
            ]
        elif rule["op"] == "design_contradiction":
            subjects = [a for a in nodes.values() if a["type"] == "component"]
        else:
            raise ValueError("Unknown proposal operation")
        for subject in sorted(subjects, key=lambda a: a["id"]):
            units = [
                a
                for a in nodes.values()
                if a["type"] == "software_unit"
                and (
                    a["attributes"]["component"] == subject["id"]
                    or any(
                        e["src"] == a["id"]
                        and e["dst"] == subject["id"]
                        and e["type"] == "implements"
                        for e in edges
                    )
                )
            ]
            jobs.append(
                {
                    "id": rule["id"] + "." + subject["id"],
                    "mode": "ai",
                    "title": rule["id"] + " proposal — " + subject["id"],
                    "query": "proposal_pack",
                    "prompt": rule["prompt"],
                    "allowed_kinds": ["suggested"],
                    "max_claims": 3,
                    "synthesis": True,
                    "query_params": {
                        "subject": subject["id"],
                        "proposal_rule": rule["id"],
                        "unit_ids": [u["id"] for u in units],
                        "design_context": [
                            {
                                "document": d["doc_id"],
                                "sha256": d["document_sha256"],
                                "claims": [
                                    c
                                    for s in d["sections"]
                                    if subject["id"] in s["cited_revisions"]
                                    or any(u["id"] in s["cited_revisions"] for u in units)
                                    for c in s["claims"]
                                ],
                            }
                            for d in documents
                            if d["doc_id"] in ("sad", "sdd")
                        ]
                        if rule["id"] == "L03"
                        else [],
                    },
                }
            )
    return jobs


def propose(
    graph: dict, documents: list[dict], root: Path = Path("out/proposals"), llm: LLM | None = None
) -> dict:
    llm = llm or LLM("mock")
    sections = [generate_section(job, graph, {}, llm) for job in proposal_jobs(graph, documents)]
    result = {
        "status": "proposed — human review required",
        "sections": sections,
        "cost_usd": llm.run_spend,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "proposals.json").write_text(json.dumps(result, indent=2))
    text = (
        "# Review proposals\n\nAll entries are suggestions. "
        "No source-system update or approval is implied.\n\n"
    )
    text += "\n".join(s["markdown"] for s in sections)
    (root / "proposals.md").write_text(text)
    return result
