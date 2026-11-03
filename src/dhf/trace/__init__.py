"""Deterministic traceability and declarative gap rules."""

from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml


def confirmed_links(graph: dict) -> list[dict]:
    return [e for e in graph["links"] if e["origin"] in ("explicit", "human_confirmed")]


def latest_results(graph: dict, release: str | None = None, level: str | None = None) -> list[dict]:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    results = {}
    for a in graph["artifacts"]:
        if a["type"] != "test_result" or (release and a["attributes"].get("release") != release):
            continue
        tc = a["attributes"]["test_case"]
        if level and nodes[tc]["attributes"].get("level") != level:
            continue
        order = (a["attributes"].get("completed_at", ""), a["id"])
        if tc not in results or order > (
            results[tc]["attributes"].get("completed_at", ""),
            results[tc]["id"],
        ):
            results[tc] = a
    return sorted(results.values(), key=lambda a: a["attributes"]["test_case"])


def results_summary(graph: dict, release: str, level: str | None = None) -> dict:
    results = latest_results(graph, release, level)
    counts = Counter(a["attributes"]["outcome"] for a in results)
    return {
        "release": release,
        "total": len(results),
        "passed": counts["Passed"],
        "failed": counts["Failed"],
        "blocked": counts["Blocked"],
        "not_run": counts["NotExecuted"] + counts["NotRun"],
    }


def rtm(graph: dict, release: str = "1.1") -> list[dict]:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    results = {a["attributes"]["test_case"]: a for a in latest_results(graph, release)}
    rows = []
    for req in sorted(
        (a for a in nodes.values() if a["type"] == "software_req"), key=lambda a: a["id"]
    ):
        id = req["id"]

        def incoming(kind: str, types: tuple[str, ...], id: str = id) -> list[str]:
            return sorted(
                {
                    e["src"]
                    for e in edges
                    if e["dst"] == id and e["type"] == kind and nodes[e["src"]]["type"] in types
                }
            )

        tests = incoming("verifies", ("test_case",))
        rows.append(
            {
                "requirement": id,
                "revision": req["source"]["revision"],
                "components": sorted(
                    e["dst"] for e in edges if e["src"] == id and e["type"] == "allocated_to"
                ),
                "tests": tests,
                "changes": incoming("implements", ("code_change",)),
                "units": incoming("implements", ("software_unit",)),
                "results": [
                    {
                        "test_case": tc,
                        "result": results[tc]["id"],
                        "outcome": results[tc]["attributes"]["outcome"],
                    }
                    for tc in tests
                    if tc in results
                ],
            }
        )
    return rows


def coverage(graph: dict, release: str = "1.1") -> dict:
    rows = rtm(graph, release)
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    verified = {r["requirement"] for r in rows if r["tests"]}
    controls = {
        e["dst"]
        for e in edges
        if e["type"] == "implements"
        and e["src"] in verified
        and nodes[e["dst"]]["type"] == "risk_control"
    }
    hazards = {e["dst"] for e in edges if e["type"] == "mitigates" and e["src"] in controls}

    def ratio(n: int, d: int) -> dict:
        return {"covered": n, "total": d, "percent": round(n / d * 100, 2) if d else 0.0}

    return {
        "srs_to_test": ratio(len(verified), len(rows)),
        "srs_to_code": ratio(sum(bool(r["changes"]) for r in rows), len(rows)),
        "hazard_to_control_to_verification": ratio(
            len(hazards), sum(a["type"] == "hazard" for a in nodes.values())
        ),
    }


def rule_subjects(rule: dict, artifacts: list[dict]) -> list[dict]:
    """Artifacts a rule inspects: its types, attribute filters and optional source systems."""
    return [
        a
        for a in sorted(artifacts, key=lambda a: a["id"])
        if a["type"] in rule["types"]
        and all(a["attributes"].get(k) == v for k, v in rule.get("attrs", {}).items())
        and not any(a["attributes"].get(k) == v for k, v in rule.get("not_attrs", {}).items())
        and (not rule.get("sources") or a["source"]["system"] in rule["sources"])
    ]


def can_carry(artifact: dict, link: str) -> bool:
    """Whether the artifact's source can hold `link` at all.

    Sources that declare their link classes (document baselines) cannot fail rules on any
    other link; ADO, git and fixture evidence can carry every class, so an absent link there
    is a real gap, even when nothing at all is linked."""
    classes = artifact["attributes"].get("link_classes")
    return classes is None or link in classes


def evaluate_rules(graph: dict, rules: list[dict]) -> list[dict]:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    findings = []
    for rule in rules:
        for a in rule_subjects(rule, graph["artifacts"]):
            attrs = a["attributes"]
            operation = rule["op"]
            if operation == "missing_link" and not can_carry(a, rule["link"]):
                continue  # not assessable for this artifact's source; never a gap
            if operation == "missing_link":
                anchor, peer = ("dst", "src") if rule["direction"] == "in" else ("src", "dst")
                flagged = not any(
                    e[anchor] == a["id"]
                    and e["type"] == rule["link"]
                    and nodes[e[peer]]["type"] in rule["peer_types"]
                    for e in edges
                )
            elif operation == "soup_requirements":
                flagged = not any(
                    e["type"] == "depends_on"
                    and a["id"] in (e["src"], e["dst"])
                    and nodes[e["dst"] if e["src"] == a["id"] else e["src"]]["type"]
                    == "software_req"
                    for e in edges
                ) or not attrs.get("known_anomaly_evaluation")
            elif operation == "match":
                flagged = True
            elif operation == "attr_present":
                flagged = bool(attrs.get(rule["attr"]))
            elif operation == "outdated_verification":
                passed = [
                    r
                    for r in nodes.values()
                    if r["type"] == "test_result"
                    and r["attributes"]["test_case"] == a["id"]
                    and r["attributes"]["outcome"] == "Passed"
                    and r["attributes"].get("completed_at")  # undated results prove no timing
                ]
                passed.sort(key=lambda r: r["attributes"].get("completed_at", ""))
                reqs = [
                    nodes[e["dst"]]
                    for e in edges
                    if e["src"] == a["id"] and e["type"] == "verifies"
                ]
                flagged = bool(passed) and any(
                    datetime.fromisoformat(
                        max(
                            r["attributes"].get(
                                "requirement_history",
                                [{"changed_at": r["attributes"]["changed_at"]}],
                            ),
                            key=lambda h: h["revision"] if "revision" in h else 0,
                        )["changed_at"].replace("Z", "+00:00")
                    )
                    > datetime.fromisoformat(
                        passed[-1]["attributes"]["completed_at"].replace("Z", "+00:00")
                    )
                    for r in reqs
                )
            else:
                raise ValueError("Unknown declarative rule operation")
            if flagged:
                findings.append(
                    {
                        "rule": rule["id"],
                        "artifact_id": a["id"],
                        "message": rule["title"],
                        "action": rule.get("action", "Review the evidence gap."),
                        "source_url": a["source"]["url"],
                        "revision": a["source"]["revision"],
                    }
                )
    return findings


def unassessable_rules(graph: dict, rules: list[dict]) -> list[str]:
    """Missing-link rules none of whose subjects come from a source able to carry the link.

    Decided by what each source declares (document imports list their link classes), not by
    which links happen to exist, so 'nothing is linked' in ADO stays a reported gap."""
    return [
        rule["id"]
        for rule in rules
        if rule["op"] == "missing_link"
        and (subjects := rule_subjects(rule, graph["artifacts"]))
        and not any(can_carry(a, rule["link"]) for a in subjects)
    ]


def gaps(graph: dict, rules_path: Path = Path("specs/rules/gaps.yaml")) -> list[dict]:
    return evaluate_rules(graph, yaml.safe_load(rules_path.read_text())["rules"])


def score_findings(findings: list[dict], expected: dict[str, list[str]]) -> dict:
    actual = {(f["rule"], f["artifact_id"]) for f in findings}
    wanted = {(rule, id) for rule, ids in expected.items() for id in ids if rule.startswith("G")}
    tp = len(actual & wanted)
    return {
        "precision": tp / len(actual) if actual else float(not wanted),
        "recall": tp / len(wanted) if wanted else 1.0,
        "true_positive": tp,
        "false_positive": len(actual - wanted),
        "false_negative": len(wanted - actual),
    }
