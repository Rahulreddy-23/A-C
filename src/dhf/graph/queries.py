"""Pure named evidence queries. IDs and facts are deterministic; prose is downstream."""

from dhf.llm import canonical
from dhf.models.values import ID_PATTERN, fact_numbers
from dhf.trace import confirmed_links, coverage, gaps, latest_results, results_summary, rtm


def query(graph: dict, name: str, params: dict) -> dict:
    release = params.get("release", "1.1")
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)

    def types(*kinds: str) -> list[dict]:
        return [a for a in graph["artifacts"] if a["type"] in kinds]

    def linked(artifacts: list[dict]) -> list[dict]:
        ids = {a["id"] for a in artifacts}
        neighbors = {e["src"] for e in edges if e["dst"] in ids} | {
            e["dst"] for e in edges if e["src"] in ids
        }
        return [nodes[id] for id in sorted(ids | neighbors)]

    results = latest_results(graph, release)
    facts = {}
    if name == "purpose_scope":
        evidence = types("user_need")
        facts = {
            "release": release,
            "scope": "System verification of the Kestrel controller",
            "verification_runs": [
                a["id"] for a in types("test_run") if a["attributes"].get("release") == release
            ],
            "results_reported_in": "Summary of results and Results by requirement sections",
        }
    elif name == "references":
        evidence = types("software_req") + [
            a for a in types("test_run") if a["attributes"].get("release") == release
        ]
        facts = {
            "rows": [
                {"id": a["id"], "revision": a["source"]["revision"], "title": a["title"]}
                for a in evidence
            ]
        }
    elif name == "test_environment":
        evidence = [a for a in types("test_run") if a["attributes"].get("release") == release]
        # Unique environment values prevent unrelated retest additions changing the section.
        facts = {
            "rows": [
                {"environment": env}
                for env in sorted({a["attributes"]["environment"] for a in evidence})
            ]
        }
    elif name == "test_results_summary":
        evidence = results
        facts = {
            "rows": [results_summary(graph, release)],
            "summary": results_summary(graph, release),
        }
    elif name == "results_by_requirement":
        rows = rtm(graph, release)
        ids = {r["requirement"] for r in rows} | {v["result"] for r in rows for v in r["results"]}
        ids |= {
            id for r in rows for key in ("components", "units", "changes", "tests") for id in r[key]
        }
        evidence = [nodes[id] for id in sorted(ids)]
        facts = {"rows": rows}
    elif name == "failed_results_with_defects":
        adverse = [a for a in results if a["attributes"]["outcome"] in ("Failed", "Blocked")]
        evidence = linked(adverse)
        facts = {
            "summary": results_summary(graph, release),
            "failed_results": [a["id"] for a in adverse],
            "rows": [
                {
                    "result": a["id"],
                    "case": a["attributes"]["test_case"],
                    "outcome": a["attributes"]["outcome"],
                    "requirements": [
                        e["dst"]
                        for e in edges
                        if e["src"] == a["attributes"]["test_case"] and e["type"] == "verifies"
                    ],
                    "defects": [
                        e["dst"]
                        for e in edges
                        if e["src"] == a["id"] and e["type"] == "reports_defect"
                    ]
                    or "none — see G05",
                }
                for a in adverse
            ],
            "recorded_defect_links": [
                {"result": e["src"], "defect": e["dst"], "origin": e["origin"]}
                for e in edges
                if e["type"] == "reports_defect" and e["src"] in {a["id"] for a in results}
            ],
        }
    elif name == "retest_results":
        evidence = results
        facts = {
            "rows": [
                {
                    "case": a["attributes"]["test_case"],
                    "result": a["id"],
                    "outcome": a["attributes"]["outcome"],
                }
                for a in results
                if nodes[a["attributes"]["run"]]["attributes"]["is_retest"]
            ]
        }
    elif name == "residual_anomalies":
        evidence = [a for a in types("defect") if a["attributes"]["state"] != "Closed"]
        facts = {
            "open_count": len(evidence),
            "residual_ids": [a["id"] for a in evidence if a["attributes"]["residual_listed"]],
        }
    elif name == "verification_gaps":
        ids = {f["artifact_id"] for f in gaps(graph) if f["rule"] in ("G01", "G04", "G07", "G11")}
        evidence = [nodes[id] for id in sorted(ids)]
        facts = {
            "rows": [f for f in gaps(graph) if f["artifact_id"] in ids],
            "coverage": coverage(graph, release),
        }
    elif name == "release_readiness_facts":
        evidence = linked(
            [a for a in results if a["attributes"]["outcome"] in ("Failed", "Blocked")]
        )
        evidence += [a for a in types("defect") if a["attributes"]["state"] != "Closed"]
        facts = {
            "summary": results_summary(graph, release),
            "coverage": coverage(graph, release),
            "gap_count": len(gaps(graph)),
            "gap_findings": [
                {
                    "rule": rule,
                    "artifacts": [f["artifact_id"] for f in gaps(graph) if f["rule"] == rule],
                }
                for rule in sorted({f["rule"] for f in gaps(graph)})
            ],
        }
    elif name == "evidence_index":
        evidence = [
            a for a in types("test_run", "test_result") if a["attributes"].get("release") == release
        ]
        facts = {
            "rows": [
                {"id": a["id"], "revision": a["source"]["revision"], "hash": a["content_hash"]}
                for a in evidence
            ]
        }
    elif name == "rtm":
        evidence = types("software_req", "code_change", "test_case", "test_result")
        facts = {"rows": rtm(graph, release), "coverage": coverage(graph, release)}
    else:
        from dhf.graph.design import design_query

        design = design_query(graph, name, params)
        facts, evidence = design["facts"], design["evidence"]
    selected = {a["id"]: a for a in evidence}
    # Keep referenced context in the pack, including when prose names a component.
    pending = list(selected.values())
    while pending:
        a = pending.pop()
        for id in ID_PATTERN.findall(a["body"]):
            id = id.rstrip(".")
            if id in nodes and id not in selected:
                selected[id] = nodes[id]
                pending.append(nodes[id])
    evidence = sorted(selected.values(), key=lambda a: a["id"])
    # Source numerical values are injected as facts for the numeric validator; never computed by AI.
    facts["source_numbers"] = sorted(
        fact_numbers([{"body": a["body"], "attributes": a["attributes"]} for a in evidence])
    )
    return {"facts": facts, "evidence": evidence}


def stable_pack(pack: dict) -> dict:
    """Retrieval timestamps are provenance, not prompt inputs or semantic changes."""
    return {
        "facts": pack["facts"],
        "evidence": [
            {**a, "source": {k: v for k, v in a["source"].items() if k != "retrieved_at"}}
            for a in pack["evidence"]
        ],
    }


def fingerprint(pack: dict) -> str:
    import hashlib

    return hashlib.sha256(canonical(stable_pack(pack)).encode()).hexdigest()


def prompt_pack(pack: dict) -> dict:
    """Human-labelled, compact view; canonical provenance stays in the manifest."""

    def display(key: str, value: object) -> object:
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, dict):
            return {k.replace("_", " ").capitalize(): display(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [display(key, v) for v in value]
        return value

    labels = {
        "residual_listed": "Listed as residual anomaly",
        "state": "Status",
        "severity": "Severity",
        "acceptance_criteria": "Acceptance criteria",
        "completed_at": "Completed at",
        "test_case": "Test case",
        "is_retest": "Retest",
    }
    evidence = []
    for a in pack["evidence"]:
        attrs = a["attributes"]
        properties = {
            labels.get(k, k.replace("_", " ").capitalize()): display(k, v)
            for k, v in attrs.items()
            if k not in ("synthetic", "steps", "requirement_history", "changed_at")
        }
        evidence.append(
            {
                "id": a["id"],
                "title": a["title"],
                "body": a["body"],
                "revision": a["source"]["revision"],
                "attributes": {"synthetic": attrs.get("synthetic", False)},
                "properties": properties,
            }
        )
    return {"facts": pack["facts"], "evidence": evidence}
