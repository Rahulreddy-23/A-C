"""Deterministic synthetic evaluation and an evidence-index clause appendix."""

import json
import re
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

from dhf.generate import expand_sections, finish_section, load_spec
from dhf.graph.queries import query
from dhf.models import Claims
from dhf.models.values import ID_PATTERN
from dhf.trace import coverage, gaps, score_findings
from dhf.trace.consistency import consistency, legacy_design


def clause_coverage(documents: list[dict]) -> dict:
    sections = {d["doc_id"] + "." + s["id"]: s for d in documents for s in d["sections"]}
    rows = []
    for clause in yaml.safe_load(Path("specs/standards/clause_coverage.yaml").read_text())[
        "clauses"
    ]:
        selected = {
            id: s
            for id, s in sections.items()
            if any(fnmatchcase(id, p) for p in clause["sections"])
        }
        evidence = sorted({id for s in selected.values() for id in s["cited_revisions"]})
        status = "draft evidence indexed" if evidence else "UNCOVERED"
        if clause.get("requires_results") and not any(
            s["facts"].get("summary", {}).get("total", 0) for s in selected.values()
        ):
            status = "UNCOVERED — no recorded results"
        if clause.get("requires_human"):
            status = (
                "human review recorded"
                if selected
                and all(
                    s.get("review_resolution", {}).get("status") == "reviewed"
                    for s in selected.values()
                )
                else "UNCOVERED — human assessment pending"
            )
        rows.append(
            {
                "clause": clause["id"],
                "topic": clause["topic"],
                "sections": sorted(selected),
                "evidence": evidence,
                "status": status,
            }
        )
    return {
        "notice": (
            "Draft evidence index only. Section presence does not establish compliance; "
            "the QMS reviewer must assess the licensed standards, completeness and approvals."
        ),
        "rows": rows,
    }


def clause_markdown(report: dict) -> str:
    text = (
        "# Regulatory clause evidence appendix\n\n"
        + report["notice"]
        + "\n\n| Clause | Topic | Sections | Evidence | Status |\n|---|---|---|---|---|\n"
    )
    return text + "".join(
        "| "
        + " | ".join(
            [
                r["clause"],
                r["topic"],
                ", ".join(r["sections"]) or "—",
                ", ".join(r["evidence"]) or "—",
                r["status"],
            ]
        )
        + " |\n"
        for r in report["rows"]
    )


def set_score(actual: set, expected: set) -> dict:
    tp, fp, fn = len(actual & expected), len(actual - expected), len(expected - actual)
    return {
        "precision": tp / (tp + fp) if tp + fp else (1.0 if not expected else 0.0),
        "recall": tp / (tp + fn) if tp + fn else 1.0,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
    }


def impact_score(reports: list[dict] | None, expected: dict) -> dict:
    if reports is None:
        return {"status": "pending — no saved pre-regeneration report"}
    actual = {
        (
            r["document"],
            s["id"],
            s["status"],
            tuple(sorted({c["artifact"] for c in s["causes"] if c["artifact"]})),
        )
        for r in reports
        if r["document"] in expected
        for s in r["sections"]
    }
    target = {
        (doc, id, s["status"], tuple(s["artifacts"]))
        for doc, rows in expected.items()
        for id, s in rows.items()
    }
    return {"status": "scored", **set_score(actual, target)}


def normalize_links(markdown: str) -> str:
    # Environment-specific URLs differ; citation labels/revisions and all visible text remain exact.
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"[\1](SOURCE)", markdown)


def evaluate(
    graph: dict,
    baseline: dict,
    documents: list[dict],
    markdowns: dict[str, str],
    reports: list[dict] | None = None,
) -> dict:
    nodes = {a["id"] for a in graph["artifacts"]}
    mixes = []
    effort_config = yaml.safe_load(Path("specs/metrics/manual_effort.yaml").read_text())
    unknown = set()
    schema_errors = []
    for doc in documents:
        counts = Counter()
        claims = []
        text = re.sub(r"<!--.*?-->", "", markdowns[doc["doc_id"]], flags=re.S)
        unknown.update(
            id.rstrip(".") for id in ID_PATTERN.findall(text) if id.rstrip(".") not in nodes
        )
        for section in doc["sections"]:
            claims.extend(section["claims"])
            counts.update(c["kind"] for c in section["claims"])
            unknown.update(
                id for c in section["claims"] for id in c["citations"] if id not in nodes
            )
        try:
            Claims.model_validate({"claims": claims})
        except ValueError:
            schema_errors.append(doc["doc_id"])
        total = sum(counts.values())
        section_types = Counter(s["mode"] for s in doc["sections"])
        baseline_hours = sum(
            section_types[k] * hours for k, hours in effort_config["hours_per_section"].items()
        )
        telemetry = doc.get("telemetry", {})
        calls = telemetry.get("calls", 0)
        hits = telemetry.get("cache_hits", 0)
        mixes.append(
            {
                "document": doc["doc_id"],
                "claims": total,
                "mix_percent": {
                    k: round(100 * counts[k] / total, 2) if total else 0.0
                    for k in ("sourced", "inferred", "suggested")
                },
                "validation": {k: len(v) for k, v in doc["validation"].items()},
                "cost_usd": doc["llm_cost_usd"],
                "seconds": telemetry.get("seconds"),
                "calls": calls,
                "cache_hits": hits,
                "cache_hit_rate": round(hits / (hits + calls), 4) if hits + calls else None,
                "claim_support": doc.get(
                    "claim_support",
                    {"support_rate": None, "counts": {}, "status": "pending — not sampled"},
                ),
                "effort": {
                    "section_counts": dict(section_types),
                    "baseline_hours": round(baseline_hours, 2),
                    "estimated_hours_saved": round(
                        max(0, baseline_hours - telemetry.get("seconds", 0) / 3600), 2
                    ),
                    "assumptions": effort_config,
                },
                "ai_unavailable": [
                    s["id"] for s in doc["sections"] if s["status"] == "ai_unavailable"
                ],
            }
        )
    key = yaml.safe_load(Path("data/synthetic/expected_gaps.yaml").read_text())
    history = legacy_design(Path("data/synthetic/sad_v1.md").read_text())
    historical = consistency(baseline, [history])
    observed = set()
    for f in historical:
        observed.update(
            (f["rule"], id)
            for id in (
                [f["artifact"]]
                if "artifact" in f
                else [*f.get("missing", []), *f.get("unexpected", [])]
            )
        )
    golden = json.loads(Path("eval/golden/design_deterministic.json").read_text())
    golden.update({"sstr": json.loads(Path("eval/golden/sstr_deterministic.json").read_text())})
    golden_results = {}
    for doc, expected in golden.items():
        actual = {
            s["id"]: normalize_links(
                finish_section(
                    s,
                    query(
                        baseline,
                        s["query"],
                        {
                            "release": "1.1",
                            **s.get("query_params", {}),
                            **({"entity": s["entity"]} if s.get("entity") else {}),
                        },
                    ),
                    [],
                    [],
                )["markdown"]
            )
            for s in expand_sections(load_spec(doc), baseline)
            if s["id"] in expected
        }
        failures = sorted(
            id for id, value in expected.items() if actual.get(id) != normalize_links(value)
        )
        golden_results[doc] = {"checked": len(expected), "mismatches": failures}
    return {
        "unknown_ids": sorted(unknown),
        "unknown_id_count": len(unknown),
        "schema_errors": schema_errors,
        "documents": mixes,
        "gap_detection": score_findings(gaps(baseline), key),
        "gap_scope": "synthetic baseline snapshot before change_1",
        "current_gap_count": len(gaps(graph)),
        "coverage": coverage(graph),
        "impact_detection": impact_score(
            reports,
            yaml.safe_load(Path("data/synthetic/scenarios/change_1.yaml").read_text())[
                "expected_sections"
            ],
        ),
        "consistency": {
            "current_findings": consistency(graph, documents),
            "historical_sad_v1": historical,
            "historical_score": set_score(
                observed, {(r, id) for r in ("C01", "C04") for id in key[r]}
            ),
        },
        "deterministic_goldens": golden_results,
        "claims_scope": (
            "typed/cited structural checks; semantic support is pending live human verification"
        ),
        "clause_coverage": clause_coverage(documents),
    }


def metrics_markdown(result: dict) -> str:
    text = (
        "# DHF evaluation metrics\n\n"
        f"Unknown/invented IDs: **{result['unknown_id_count']}**. "
        f"Schema errors: {len(result['schema_errors'])}.\n\n"
    )
    gap, impact = result["gap_detection"], result["impact_detection"]
    text += (
        f"Baseline gaps: precision {gap['precision']:.2f}, recall {gap['recall']:.2f} "
        f"({gap['true_positive']} exact findings). Current gaps: "
        f"{result['current_gap_count']}.\n\n"
    )
    text += "Saved change_1 impact: "
    if impact["status"] == "scored":
        text += (
            f"precision {impact['precision']:.2f}, recall {impact['recall']:.2f}; "
            f"{impact['true_positive']} exact section/status/cause records"
        )
    else:
        text += impact["status"]
    text += (
        ". Regression against a reviewer-audited expectation; not independent accuracy.\n\n"
        "Historical sad-v1 consistency: "
    )
    text += json.dumps(result["consistency"]["historical_score"])
    text += f". Current draft findings: {len(result['consistency']['current_findings'])}.\n\n"
    text += (
        "| Document | Claims | Sourced % | Inferred % | Suggested % | Reject / downgrade | "
        "USD | Seconds | Cache hit rate |\n"
        "|---|---:|---:|---:|---:|---|---:|---:|---:|\n"
    )
    for d in result["documents"]:
        hit = d["cache_hit_rate"] if d["cache_hit_rate"] is not None else "—"
        text += f"| {d['document']} | {d['claims']} | "
        text += " | ".join(str(d["mix_percent"][k]) for k in ("sourced", "inferred", "suggested"))
        text += (
            f" | {d['validation']['rejected']} / {d['validation']['downgraded']} | "
            f"{d['cost_usd']:.6f} | {d['seconds']:.3f} | {hit} |\n"
        )
    text += (
        "\n| Document | AI / deterministic / human sections | Assumed authoring hours | "
        "Estimated hours saved | Support rate | Supported / partial / unsupported | "
        "Coverage verified / sampled eligible (document eligible); "
        "unverified rationale | Verifier USD / seconds |\n"
        "|---|---|---:|---:|---|---|---|---|\n"
    )
    for d in result["documents"]:
        effort, support = d["effort"], d["claim_support"]
        section_counts = " / ".join(
            str(effort["section_counts"].get(k, 0)) for k in ("ai", "deterministic", "human")
        )
        rate = (
            f"{support['support_rate']:.1%}"
            if support.get("support_rate") is not None
            else "pending"
        )
        counts = " / ".join(
            str(support.get("counts", {}).get(k, 0))
            for k in ("supported", "partial", "unsupported")
        )
        coverage = support.get("coverage", {})
        text += (
            f"| {d['document']} | {section_counts} | {effort['baseline_hours']} | "
            f"{effort['estimated_hours_saved']} | {rate} | {counts} | "
            f"{coverage.get('verified', 0)} / {coverage.get('sampled_eligible', 0)} "
            f"({coverage.get('document_eligible', 'pending')}); "
            f"{support.get('rationale_unverified_count', 0)} | "
            f"{support.get('cost_usd', 0):.6f} / {support.get('seconds', 0):.3f} |\n"
        )
    if result["documents"]:
        text += "\n" + result["documents"][0]["effort"]["assumptions"]["notice"] + "\n"
        text += (
            "Hours per section type: `"
            + json.dumps(result["documents"][0]["effort"]["assumptions"]["hours_per_section"])
            + "`. Support rates use returned verdicts only; coverage states the sampled eligible "
            "denominator. Unavailable checks remain visible. Support assessments are advisory; "
            "mock rates are lexical fixture checks.\n"
        )
    text += "\nCoverage: `" + json.dumps(result["coverage"], sort_keys=True) + "`.\n\n"
    text += "Deterministic baseline goldens: `"
    text += json.dumps(result["deterministic_goldens"], sort_keys=True)
    text += "`.\n\n" + result["claims_scope"] + ". No approval is implied.\n"
    return text
