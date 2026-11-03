"""Risk and review evidence queries; human review inputs never come from a model."""

from dhf.trace import confirmed_links, gaps, latest_results


def risk_rows(graph: dict, hazard: str | None = None) -> list[dict]:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    rows = []
    for h in sorted(
        (
            a
            for a in nodes.values()
            if a["type"] == "hazard" and (hazard is None or a["id"] == hazard)
        ),
        key=lambda a: a["id"],
    ):
        controls = {e["src"] for e in edges if e["dst"] == h["id"] and e["type"] == "mitigates"}
        reqs = {
            e["src"]
            for e in edges
            if e["dst"] in controls
            and e["type"] == "implements"
            and nodes[e["src"]]["type"] == "software_req"
        }
        units = {
            e["src"]
            for e in edges
            if e["dst"] in reqs
            and e["type"] == "implements"
            and nodes[e["src"]]["type"] == "software_unit"
        }
        components = {nodes[u]["attributes"]["component"] for u in units}
        tests = {e["src"] for e in edges if e["dst"] in reqs and e["type"] == "verifies"}
        rows.append(
            {
                "hazard": h["id"],
                "hazard_name": h["title"],
                "severity": h["attributes"].get("severity", "Not recorded in the source"),
                "components": sorted(components),
                "units": sorted(units),
                "function": "; ".join(
                    nodes[c]["attributes"]["responsibility"] for c in sorted(components)
                ),
                "controls": [{"id": c, "title": nodes[c]["title"]} for c in sorted(controls)],
                "requirements": sorted(reqs),
                "verification": sorted(tests),
                "analysis_rows": sorted(units),
                "residual_risk": "Human assessment required — no acceptance recorded",
            }
        )
    return rows


def risk_gaps(graph: dict, modes: list[dict] | None = None) -> list[dict]:
    from pathlib import Path

    import yaml

    definitions = {
        r["op"]: r
        for r in yaml.safe_load(Path("specs/rules/risk.yaml").read_text(encoding="utf-8"))["rules"]
    }
    rows = risk_rows(graph)
    findings = []

    def emit(op: str, artifact: str) -> None:
        definition = definitions[op]
        findings.append(
            {"rule": definition["id"], "artifact": artifact, "action": definition["action"]}
        )

    for row in rows:
        if not row["controls"]:
            emit("missing_control", row["hazard"])
        if not row["verification"]:
            emit("missing_verification", row["hazard"])
        if not any(
            row["hazard"] in m["citations"]
            and m["text"].startswith("Failure mode:")
            and m.get("kind") == "human_confirmed"
            for m in (modes or [])
        ):
            emit("missing_confirmed_mode", row["hazard"])
    # Evaluate each control separately so a verified sibling cannot hide a control gap.
    nodes = {a["id"]: a for a in graph["artifacts"]}
    edges = confirmed_links(graph)
    for control in (a for a in nodes.values() if a["type"] == "risk_control"):
        reqs = {
            e["src"]
            for e in edges
            if e["dst"] == control["id"]
            and e["type"] == "implements"
            and nodes[e["src"]]["type"] == "software_req"
        }
        if not any(e["dst"] in reqs and e["type"] == "verifies" for e in edges):
            emit("missing_verification", control["id"])
    return findings


def review_query(graph: dict, name: str, params: dict) -> dict:
    nodes = {a["id"]: a for a in graph["artifacts"]}
    if name in ("sfmea_functions", "sfmea_function_cells"):
        from pathlib import Path

        import yaml

        unit = nodes[params["entity"]]
        primary = yaml.safe_load(Path("specs/risk/functions.yaml").read_text(encoding="utf-8"))[
            unit["id"]
        ]
        hazards = [r for r in risk_rows(graph) if unit["id"] in r["units"]]
        ids = {unit["id"], unit["attributes"]["component"]}
        ids.update(
            id
            for r in hazards
            for id in [
                r["hazard"],
                *r["requirements"],
                *r["verification"],
                *(c["id"] for c in r["controls"]),
            ]
        )
        evidence = [nodes[id] for id in sorted(ids)]
        row = {
            "unit": unit["id"],
            "component": unit["attributes"]["component"],
            "function": primary,
            "hazards": [
                {"id": r["hazard"], "name": r["hazard_name"], "source_severity": r["severity"]}
                for r in hazards
            ],
            "controls": [c for r in hazards for c in r["controls"]],
            "verification": sorted({t for r in hazards for t in r["verification"]}),
            "requirements": sorted({id for r in hazards for id in r["requirements"]}),
            "residual_risk": "Human assessment required — no acceptance recorded",
        }
        facts = {
            "rows": [row],
            "source_revisions": {a["id"]: a["source"]["revision"] for a in evidence},
        }
        if name == "sfmea_function_cells":
            facts.update(
                {
                    "risk_authoring": True,
                    "unit_function": primary,
                    "unit": unit["id"],
                    "cell_labels": [
                        "Failure mode",
                        "Cause",
                        "Local effect",
                        "System effect",
                        "Recommended action",
                    ],
                }
            )
        return {"facts": facts, "evidence": evidence}
    if name.startswith("sfmea_"):
        rows = risk_rows(graph, params.get("entity"))
        ids = {
            id
            for row in rows
            for id in [
                row["hazard"],
                *row["components"],
                *row["units"],
                *row["requirements"],
                *row["verification"],
                *(c["id"] for c in row["controls"]),
            ]
        }
        ids.update(
            a["id"]
            for a in latest_results(graph, params.get("release", "1.1"))
            if a["attributes"]["test_case"] in ids
        )
        evidence = [nodes[id] for id in sorted(ids)]
        if name == "sfmea_cells":
            return {
                "facts": {
                    "risk_authoring": True,
                    "cell_labels": [
                        "Failure mode",
                        "Cause",
                        "Local effect",
                        "System effect",
                        "Recommended action",
                    ],
                    "hazard": params["entity"],
                    "source_revisions": {a["id"]: a["source"]["revision"] for a in evidence},
                },
                "evidence": evidence,
            }
        if name == "sfmea_gaps":
            return {"facts": {"rows": risk_gaps(graph)}, "evidence": evidence}
        return {"facts": {"rows": rows}, "evidence": evidence}
    review = params.get("review_input", {})
    if name == "drr_identification":
        required = {"type", "date", "baseline", "participants"}
        if (
            not required <= review.keys()
            or not isinstance(review["participants"], list)
            or not review["participants"]
        ):
            raise ValueError("Review input requires type, date, baseline and nonempty participants")
        return {
            "facts": {
                "rows": [
                    {"field": k, "value": review[k]}
                    for k in ("type", "date", "baseline", "participants")
                ]
            },
            "evidence": [],
        }
    if name == "drr_scope":
        baseline = params.get("previous_snapshot")
        if baseline is None:
            return {
                "facts": {
                    "notice": (
                        "Previous source snapshot not supplied; "
                        "compare the named baseline manually."
                    )
                },
                "evidence": [],
            }
        from dhf.graph import diff_graph

        changed = diff_graph(baseline, graph)
        ids = set().union(*changed.values())
        return {
            "facts": {
                "notice": ""
                if ids
                else (
                    f"No changes since {review.get('baseline', 'the supplied baseline')} "
                    f"(snapshot {params.get('baseline_snapshot', 1)})"
                ),
                "rows": [
                    {"artifact": id, "change": kind}
                    for kind in ("changed", "added", "removed")
                    for id in changed[kind]
                ],
            },
            "evidence": [nodes[id] for id in sorted(ids & nodes.keys())],
        }
    if name == "drr_actions":
        actions = [a for a in nodes.values() if a["type"] == "action_item"]
        return {
            "facts": {
                "rows": [
                    {
                        "id": a["id"],
                        "title": a["title"],
                        "state": a["attributes"].get("state", "Unrecorded"),
                    }
                    for a in actions
                ]
            },
            "evidence": actions,
        }
    if name in ("drr_findings", "drr_checklist", "drr_findings_table"):
        from collections import defaultdict

        from dhf.trace.consistency import consistency

        grouped = defaultdict(list)
        for finding in consistency(graph, params.get("documents", [])):
            grouped[(finding["document"], finding["rule"])].append(finding)
        summaries = [
            {
                "document": doc,
                "rule": rule,
                "count": len(items),
                "artifacts": sorted(
                    {
                        id
                        for f in items
                        for id in (
                            [f["artifact"]]
                            if f.get("artifact")
                            else [*f.get("missing", []), *f.get("unexpected", [])]
                        )
                    }
                ),
                "sections": sorted({f.get("section") for f in items if f.get("section")}),
            }
            for (doc, rule), items in sorted(grouped.items())
        ]
        priority = {"C01": 0, "C04": 0, "C02": 1, "G06": 2, "G07": 2, "G05": 3}
        drafts = [
            {
                "rule": f["rule"],
                "artifact_id": id,
                "message": f"{f['document']} baseline consistency finding",
                "action": (
                    "Reconcile the baseline with current source before recording review decisions."
                ),
            }
            for f in summaries
            for id in f["artifacts"]
        ] + gaps(graph)
        drafts.sort(key=lambda f: (priority.get(f["rule"], 4), f["rule"], f["artifact_id"]))
        if name == "drr_findings_table":
            rule_ids = [
                r["id"]
                for file in ("gaps", "consistency", "risk")
                for r in __import__("yaml").safe_load(
                    __import__("pathlib")
                    .Path(f"specs/rules/{file}.yaml")
                    .read_text(encoding="utf-8")
                )["rules"]
            ]
            all_findings = drafts + [
                {"rule": f["rule"], "artifact_id": f["artifact"], "action": f["action"]}
                for f in risk_gaps(graph)
            ]
            return {
                "facts": {
                    "rows": [
                        {
                            "rule": rule,
                            "count": sum(f["rule"] == rule for f in all_findings),
                            "artifacts": sorted(
                                {f["artifact_id"] for f in all_findings if f["rule"] == rule}
                            ),
                            "action": next(
                                (f["action"] for f in all_findings if f["rule"] == rule),
                                "No finding recorded.",
                            ),
                        }
                        for rule in rule_ids
                    ]
                },
                "evidence": [
                    nodes[id]
                    for id in sorted(
                        {f["artifact_id"] for f in all_findings if f["artifact_id"] in nodes}
                    )
                ],
            }
        facts = {
            "review_drafting": "checklist" if name == "drr_checklist" else "findings",
            "gap_findings": drafts,
            "consistency_findings": summaries,
            "impact": [
                {
                    "document": r["document"],
                    "stale": [s["id"] for s in r["sections"] if s["status"] == "stale"],
                    "possibly_affected_count": sum(
                        s["status"] == "possibly_affected" for s in r["sections"]
                    ),
                }
                for r in params.get("impact_reports", [])
            ],
        }
        return {
            "facts": facts,
            "evidence": [
                nodes[id]
                for id in sorted({f["artifact_id"] for f in facts["gap_findings"]})
                if id in nodes
            ],
        }
    raise ValueError("Unknown review query")
