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
