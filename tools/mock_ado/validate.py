"""Independent answer-key validation for the synthetic fixture."""

from pathlib import Path

import yaml


def validate_dataset() -> dict:
    data = yaml.safe_load(Path("data/synthetic/evidence.yaml").read_text())
    nodes = {a["id"]: a for a in data["artifacts"]}
    assert len(nodes) == len(data["artifacts"])
    assert all(e["src"] in nodes and e["dst"] in nodes for e in data["links"])
    edges = data["links"]

    def typed(kind: str) -> set[str]:
        return {id for id, a in nodes.items() if a["type"] == kind}

    def incoming(kind: str) -> set[str]:
        return {e["dst"] for e in edges if e["type"] == kind}

    def outgoing(kind: str) -> set[str]:
        return {e["src"] for e in edges if e["type"] == kind}

    software = typed("software_req")
    missing_tests = software - incoming("verifies")
    observed = {
        "G01": missing_tests,
        "G02": software - incoming("implements"),
        "G03": (typed("code_change") | typed("software_unit")) - outgoing("implements"),
        "G04": typed("test_case") - outgoing("verifies"),
        "G05": {id for id in typed("test_result") if nodes[id]["attributes"]["outcome"] == "Failed"}
        - outgoing("reports_defect"),
        "G06": typed("risk_control") - incoming("implements"),
        "G07": {id for id in missing_tests if nodes[id]["attributes"].get("risk_control")},
        "G08": typed("system_req") - incoming("derives_from"),
        "G09": software - outgoing("derives_from"),
        "G10": {
            id
            for id in typed("defect")
            if nodes[id]["attributes"]["state"] != "Closed"
            and not nodes[id]["attributes"]["residual_listed"]
        },
        "G11": set(),
    }
    for e in edges:
        if e["type"] != "verifies":
            continue
        req = nodes[e["dst"]]
        results = [
            nodes[id]
            for id in typed("test_result")
            if nodes[id]["attributes"]["test_case"] == e["src"]
            and nodes[id]["attributes"]["outcome"] == "Passed"
        ]
        if results:
            latest = max(results, key=lambda a: a["attributes"]["completed_at"])
            if latest["attributes"]["verified_revision"] < req["attributes"].get("revision", 1):
                observed["G11"].add(e["src"])
    key = yaml.safe_load(Path("data/synthetic/expected_gaps.yaml").read_text())
    for rule, ids in observed.items():
        assert ids == set(key[rule]), (rule, sorted(ids), key[rule])
    return {
        "artifacts": len(nodes),
        "links": len(edges),
        "answer_key": "exact",
        "rules": len(observed),
    }


if __name__ == "__main__":
    print(validate_dataset())
