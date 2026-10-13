"""Offline completeness/parity-contract checks for the human-readable tenant build pack."""

import json
from pathlib import Path

import yaml

from dhf.generate import load_prompt, sha
from dhf.generate.validator import validate_claims
from dhf.models.evidence import validate_graph
from dhf.trace import gaps, results_summary, score_findings


def check_port(root: Path = Path("port/copilot_studio")) -> dict:
    catalog = yaml.safe_load((root / "catalog.yaml").read_text())
    rules = {
        r["id"]
        for p in Path("specs/rules").glob("*.yaml")
        for r in yaml.safe_load(p.read_text())["rules"]
    }
    assert set(catalog["rules"]) == rules
    logic = (root / "deterministic_logic.md").read_text()
    assert all(f"| {id} |" in logic for id in rules)
    queries = {
        s["query"]
        for p in Path("specs/documents").glob("*.yaml")
        for s in yaml.safe_load(p.read_text())["sections"]
        if "query" in s
    } | {"proposal_pack"}
    assert set(catalog["queries"]) == queries
    query_text = (root / "query_catalog.md").read_text()
    assert all(f"| {q} |" in query_text for q in queries)
    assert len(catalog["flows"]) == 7
    assert all((root / f).is_file() for f in catalog["flows"])
    actual_prompts = {p.stem for p in Path("specs/prompts").glob("*.md")}
    assert {p["id"] for p in catalog["prompts"]} == actual_prompts
    for entry in catalog["prompts"]:
        prompt = load_prompt(f"{entry['id']}@{entry['version']}")
        assert prompt["sha256"] == entry["sha256"]
        assert (
            prompt["body"]
            == (root / entry["tool"])
            .read_text()
            .split("## Instructions (exact reference body)\n", 1)[1]
            .strip()
        )
    graph = validate_graph(json.loads((root / "contracts/canonical_graph.json").read_text()))
    score = score_findings(
        gaps(graph), yaml.safe_load((root / "contracts/answer_key.yaml").read_text())
    )
    assert score["precision"] == score["recall"] == 1.0
    assert results_summary(graph, "1.1")["passed"] == 39
    test = json.loads((root / "contracts/validator_cases.json").read_text())
    result = validate_claims(
        {"claims": test["claims"]}, test["pack"], ["sourced", "inferred", "suggested"]
    )
    assert {
        "accepted": len(result["claims"]),
        "rejected": len(result["validation"]["rejected"]),
        "downgraded": len(result["validation"]["downgraded"]),
    } == test["expected"]
    expected = yaml.safe_load((root / "contracts/change_1.yaml").read_text())["expected_sections"]
    assert (
        expected
        == yaml.safe_load(Path("data/synthetic/scenarios/change_1.yaml").read_text())[
            "expected_sections"
        ]
    )
    assert expected["sfmea"]["control_trace.HAZ-04"]["status"] == "stale"
    assert sha((root / "contracts/review_input.json").read_text()) == sha(
        Path("data/synthetic/review_input.json").read_text()
    )
    return {
        "flows": 7,
        "rules": len(rules),
        "queries": len(queries),
        "prompt_tools": len(actual_prompts),
        "reference_contracts": "pass",
        "tenant_parity": "pending",
    }


if __name__ == "__main__":
    print(json.dumps(check_port(), indent=2))
