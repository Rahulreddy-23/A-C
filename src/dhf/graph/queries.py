"""Pure named evidence queries. IDs and facts are deterministic; prose is downstream."""

from dhf.generate.validator import ID_PATTERN, fact_numbers
from dhf.llm import canonical
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
            "scope": "System verification of the synthetic Kestrel controller",
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
        evidence = [nodes[id] for id in sorted(ids)]
        facts = {"rows": rows}
    elif name == "failed_results_with_defects":
        evidence = linked([a for a in results if a["attributes"]["outcome"] == "Failed"])
        facts = {
            "summary": results_summary(graph, release),
            "failed_results": [a["id"] for a in results if a["attributes"]["outcome"] == "Failed"],
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
        evidence = [a for a in results if a["attributes"]["outcome"] == "Failed"] + types(
            "software_req"
        )
        facts = {
            "summary": results_summary(graph, release),
            "coverage": coverage(graph, release),
            "gap_count": len(gaps(graph)),
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
        raise ValueError("Unknown named query: " + name)
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
