"""Advisory claim-support assessment; original claims and readiness are preserved."""

import copy
import time
from collections import Counter
from datetime import UTC, datetime

from dhf.generate import load_prompt, require_synthetic
from dhf.generate.validator import validate_claims
from dhf.llm import LLM, canonical
from dhf.llm.tokens import estimate_tokens
from dhf.models import SupportChecks
from dhf.models.values import fact_numbers
from dhf.review import claim_key


def support_jobs(graph: dict, manifest: dict, sample: int) -> list[dict]:
    if sample < 0:
        raise ValueError("Sample must be nonnegative; zero means all eligible claims")
    nodes = {a["id"]: a for a in graph["artifacts"]}
    jobs = []
    for section in manifest["sections"]:
        for claim in section["claims"]:
            if claim["kind"] == "suggested":
                continue
            ids = claim["citations"]
            evidence = [nodes[id] for id in ids if id in nodes]
            missing = [
                id
                for id in ids
                if id not in nodes
                or nodes[id]["source"]["revision"] != section["cited_revisions"].get(id)
            ]
            jobs.append(
                {
                    "section": section["id"],
                    "claim_key": claim_key(claim),
                    "claim": claim,
                    "evidence": evidence,
                    "missing_revisions": missing,
                }
            )
    return jobs[:sample] if sample else jobs


def verify_document(graph: dict, manifest: dict, llm: LLM, sample: int = 5) -> dict:
    require_synthetic(graph, llm)  # claim text derives from the graph even without citations
    output = copy.deepcopy(manifest)
    prompt = load_prompt("verify.support@1")
    start, cost = time.monotonic(), llm.run_spend
    results = []
    all_jobs = support_jobs(graph, manifest, 0)
    jobs = all_jobs[:sample] if sample else all_jobs
    if sample < 0:
        raise ValueError("Sample must be nonnegative")
    for job in jobs:
        evidence = [
            {
                "id": a["id"],
                "body": a["body"],
                "title": a["title"],
                "revision": a["source"]["revision"],
                "attributes": a["attributes"],
            }
            for a in job["evidence"]
        ]
        pack = {
            "facts": {
                "support_subject": {"claim_key": job["claim_key"], **job["claim"]},
                "source_numbers": sorted(fact_numbers(evidence)),
            },
            "evidence": evidence,
        }
        record = {
            "section": job["section"],
            "claim_key": job["claim_key"],
            "model": llm.model_for(),
            "evidence_revisions": {a["id"]: a["source"]["revision"] for a in job["evidence"]},
        }
        try:
            if job["missing_revisions"]:
                raise ValueError("cited_revision_unavailable")
            if (
                estimate_tokens(canonical(pack) + prompt["body"])
                > prompt["max_input_tokens"] - 1000
            ):
                raise ValueError("verification_evidence_over_budget")
            raw = llm.generate(
                prompt["id"],
                prompt["version"],
                prompt["body"],
                pack,
                prompt["max_output_tokens"],
                output_schema="support.v1",
            )
            verdicts = SupportChecks.model_validate(raw).model_dump(mode="json")["results"]
            if len(verdicts) != 1 or verdicts[0]["claim_key"] != job["claim_key"]:
                raise ValueError("verification_subject_mismatch")
            verdict = verdicts[0]
            checked = validate_claims({"claims": [verdict["rationale"]]}, pack, ["suggested"])
            if not checked["claims"] or any(checked["validation"].values()):
                record["initial_rationale_validation"] = checked["validation"]
                retry = load_prompt("verify.support.retry@1")
                retry_pack = copy.deepcopy(pack)
                retry_pack["facts"]["allowed_ids"] = [a["id"] for a in evidence]
                retry_pack["facts"]["preserve_verdict"] = verdict["support"]
                record["rationale_retry"] = True
                try:
                    repaired = llm.generate(
                        retry["id"],
                        retry["version"],
                        retry["body"],
                        retry_pack,
                        retry["max_output_tokens"],
                        output_schema="support.v1",
                    )["results"]
                    if (
                        len(repaired) != 1
                        or repaired[0]["claim_key"] != job["claim_key"]
                        or repaired[0]["support"] != verdict["support"]
                    ):
                        raise ValueError("rationale_retry_subject_mismatch")
                    checked_retry = validate_claims(
                        {"claims": [repaired[0]["rationale"]]}, pack, ["suggested"]
                    )
                    if not checked_retry["claims"] or any(checked_retry["validation"].values()):
                        raise ValueError("invalid_verification_rationale")
                    checked = checked_retry
                except ValueError as error:
                    record.update(
                        rationale_unverified=True,
                        rationale_reason=str(error),
                        unverified_rationale=verdict["rationale"],
                    )
                    checked = {
                        "claims": [
                            {
                                "text": (
                                    "Verifier explanation requires human review; "
                                    "rationale validation failed."
                                ),
                                "kind": "suggested",
                                "citations": [],
                                "confidence": 0.0,
                            }
                        ],
                        "validation": record["initial_rationale_validation"],
                    }
            record.update(
                support=verdict["support"],
                rationale=checked["claims"][0],
                validation=checked["validation"],
            )
        except ValueError as error:
            record.update(support="unavailable", reason=str(error))
        results.append(record)
    counts = Counter(r["support"] for r in results)
    judged = sum(counts[k] for k in ("supported", "partial", "unsupported"))
    output["claim_support"] = {
        "advisory_only": True,
        "notice": (
            "Model judgement is reviewer assistance, not proof or a readiness gate. "
            "Mock uses lexical comparison only."
        ),
        "provider": llm.provider,
        "prompt": {k: prompt[k] for k in ("id", "version", "sha256")},
        "assessed_at": datetime.now(UTC).isoformat(),
        "results": results,
        "counts": dict(counts),
        "support_rate": counts["supported"] / judged if judged else None,
        "support_rate_denominator": judged,
        "coverage": {
            "verified": judged,
            "sampled_eligible": len(jobs),
            "document_eligible": len(all_jobs),
            "rate": judged / len(jobs) if jobs else None,
        },
        "rationale_unverified_count": sum(bool(r.get("rationale_unverified")) for r in results),
        "unavailable_reasons": dict(
            Counter(r["reason"] for r in results if r["support"] == "unavailable")
        ),
        "cost_usd": llm.run_spend - cost,
        "seconds": time.monotonic() - start,
    }
    return output


def support_comments(manifest: dict) -> list[dict]:
    claims = {claim_key(c): c for s in manifest["sections"] for c in s["claims"]}
    return [
        {
            "text": claims[r["claim_key"]]["text"],
            "note": "Advisory support assessment: "
            + r["support"]
            + ". "
            + r.get("rationale", {}).get("text", r.get("reason", "")),
        }
        for r in manifest.get("claim_support", {}).get("results", [])
        if (r["support"] != "supported" or r.get("rationale_unverified"))
        and r["claim_key"] in claims
    ]
