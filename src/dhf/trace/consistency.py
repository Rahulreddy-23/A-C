"""Pure cross-document checks; findings never imply a compliance approval."""


def component_consistency(graph: dict, documents: list[dict]) -> list[dict]:
    expected = {a["id"] for a in graph["artifacts"] if a["type"] == "component"}
    findings = []
    for document in documents:
        actual = set(document.get("component_set", []))
        if actual != expected:
            findings.append(
                {
                    "rule": "C01",
                    "document": document["doc_id"],
                    "missing": sorted(expected - actual),
                    "unexpected": sorted(actual - expected),
                }
            )
    return findings


def consistency(graph: dict, documents: list[dict]) -> list[dict]:
    """Dispatch all data-defined consistency checks against current evidence."""
    from pathlib import Path

    import yaml

    from dhf.trace import results_summary

    nodes = {a["id"]: a for a in graph["artifacts"]}
    findings = []
    rules = yaml.safe_load(Path("specs/rules/consistency.yaml").read_text())["rules"]
    for rule in rules:
        for doc in documents:
            common = {
                "rule": rule["id"],
                "document": doc["doc_id"],
                "scope": doc.get("baseline_tag", "draft"),
            }
            if rule["op"] == "component_set" and doc["doc_id"] in ("sad", "sdd", "sfmea"):
                findings += [
                    {**f, "scope": doc.get("baseline_tag", "draft")}
                    for f in component_consistency(graph, [doc])
                ]
            elif rule["op"] == "citation_revision":
                for section in doc.get("sections", []):
                    for id, revision in section["cited_revisions"].items():
                        if id not in nodes or nodes[id]["source"]["revision"] != revision:
                            findings.append(
                                {
                                    **common,
                                    "section": section["id"],
                                    "artifact": id,
                                    "reason": "unknown" if id not in nodes else "stale",
                                }
                            )
            elif rule["op"] == "result_summary" and doc["doc_id"] == "sstr":
                summary = next(
                    (
                        s["facts"].get("summary")
                        for s in doc["sections"]
                        if s["id"] == "results_summary"
                    ),
                    None,
                )
                if summary != results_summary(graph, doc["params"]["release"]):
                    findings.append(
                        {
                            **common,
                            "recorded": summary,
                            "current": results_summary(graph, doc["params"]["release"]),
                        }
                    )
            elif rule["op"] == "component_name":
                for id, name in doc.get("component_names", {}).items():
                    if id in nodes and name != nodes[id]["title"]:
                        findings.append(
                            {
                                **common,
                                "artifact": id,
                                "recorded": name,
                                "current": nodes[id]["title"],
                            }
                        )
            elif rule["op"] not in (
                "component_set",
                "citation_revision",
                "result_summary",
                "component_name",
            ):
                raise ValueError("Unknown consistency operation")
    return findings


def legacy_design(markdown: str) -> dict:
    """Import the historical synthetic SAD inventory without treating prose as approval."""
    import re

    names = dict(
        re.findall(r"^(COMP-\d+): ([^.\n]+?) (?:owns|accepts|prioritizes|supplies)", markdown, re.M)
    )
    return {"doc_id": "sad", "component_set": list(names), "component_names": names, "sections": []}
