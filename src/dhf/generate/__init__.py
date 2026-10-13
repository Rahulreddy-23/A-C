"""Specification-driven document orchestration around pure JSON pipeline steps."""

import hashlib
import json
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pydantic import ValidationError

from dhf.config import setting
from dhf.generate.validator import ID_PATTERN, validate_claims
from dhf.graph.queries import fingerprint, prompt_pack, query
from dhf.llm import LLM, BudgetExceeded, canonical, combine_usage_sources
from dhf.llm.errors import DraftingUnavailable
from dhf.llm.tokens import estimate_tokens
from dhf.models import strict_claims_schema


class EvidenceOverBudget(ValueError):
    """Only deterministic internal budget messages, never provider response text."""


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def load_spec(doc: str) -> dict:
    if not doc.replace("_", "").isalnum():
        raise ValueError("Invalid document ID")
    spec = yaml.safe_load(Path(f"specs/documents/{doc}.yaml").read_text())
    if spec["id"] != doc or len({s["id"] for s in spec["sections"]}) != len(spec["sections"]):
        raise ValueError("Invalid or duplicate spec identifiers")
    return spec


def load_prompt(reference: str) -> dict:
    id, version = reference.rsplit("@", 1)
    raw = Path("specs/prompts/" + id + ".md").read_text()
    _, head, body = raw.split("---", 2)
    meta = yaml.safe_load(head)
    if (
        meta["id"] != id
        or str(meta["version"]) != version
        or meta["output_schema"] not in ("claims.v1", "support.v1")
    ):
        raise ValueError("Prompt contract mismatch")
    return {**meta, "body": body.strip(), "sha256": sha(raw)}


def expand_sections(spec: dict, graph: dict) -> list[dict]:
    """Pure expansion of data-defined repeated component/unit sections."""
    sections = []
    pending = list(spec["sections"])
    while pending:
        first = pending.pop(0)
        if "repeat" not in first:
            sections.append(first)
            continue
        group = [first]
        while pending and pending[0].get("repeat") == first["repeat"]:
            group.append(pending.pop(0))
        for artifact in sorted(graph["artifacts"], key=lambda a: a["id"]):
            if artifact["type"] == first["repeat"] and (
                not first.get("repeat_class")
                or next(
                    a for a in graph["artifacts"] if a["id"] == artifact["attributes"]["component"]
                )["attributes"]["safety_class"]
                == first["repeat_class"]
            ):
                for group_index, section in enumerate(group):
                    sections.append(
                        {
                            **section,
                            "id": section["id"] + "." + artifact["id"],
                            "title": section["title"],
                            "heading_level": 3,
                            "group_title": artifact["id"] + ": " + artifact["title"]
                            if group_index == 0
                            else None,
                            "entity": artifact["id"],
                        }
                    )
    return sections


def partition_pack(pack: dict, budget: int) -> list[dict]:
    """Token-estimated evidence bound; never silently discard evidence."""
    groups = []
    current = {"facts": pack["facts"], "evidence": []}
    if estimate_tokens(canonical(current)) > budget:
        raise EvidenceOverBudget("Section facts exceed prompt budget; split the named query")
    nodes = {a["id"]: a for a in pack["evidence"]}

    def context(a: dict) -> list[dict]:
        selected = {a["id"]: a}
        pending = [a]
        while pending:
            item = pending.pop()
            for ref in ID_PATTERN.findall(item.get("body", "")):
                ref = ref.rstrip(".")
                if ref in nodes and ref not in selected:
                    selected[ref] = nodes[ref]
                    pending.append(nodes[ref])
        return list(selected.values())

    seen = set()
    for a in pack["evidence"]:
        if a["id"] in seen:
            continue
        expanded = {item["id"]: item for item in [*current["evidence"], *context(a)]}
        candidate = {"facts": pack["facts"], "evidence": list(expanded.values())}
        if estimate_tokens(canonical(candidate)) > budget:
            if not current["evidence"]:
                raise EvidenceOverBudget(
                    "Single artifact and context exceed prompt budget; split by unit"
                )
            groups.append(current)
            current = {"facts": pack["facts"], "evidence": context(a)}
            if estimate_tokens(canonical(current)) > budget:
                raise EvidenceOverBudget("Single artifact and context exceed prompt budget")
        else:
            current = candidate
        seen.update(item["id"] for item in current["evidence"])
    if current["evidence"] or not groups:
        groups.append(current)
    return groups


def reduce_synthesis(model_pack: dict, source_pack: dict, budget: int) -> tuple[dict, dict]:
    """Deterministic context reduction; adverse outcomes and defects retain priority."""

    def token_size(value: dict) -> int:
        # Also bound ordinary JSON transports that insert whitespace/escape Unicode.
        return max(estimate_tokens(canonical(value)), estimate_tokens(json.dumps(value)))

    if token_size(model_pack) <= budget:
        return model_pack, {"reduced": False}
    sources = {a["id"]: a for a in source_pack["evidence"]}
    priority = [
        a
        for a in model_pack["evidence"]
        if sources[a["id"]]["type"] == "defect"
        or (
            sources[a["id"]]["type"] == "test_result"
            and sources[a["id"]]["attributes"].get("outcome") in ("Failed", "Blocked")
        )
    ]
    if not priority:
        priority = model_pack["evidence"]
    required = {id.rstrip(".") for id in ID_PATTERN.findall(canonical(model_pack["facts"]))}
    compact = [
        {
            "id": a["id"],
            "title": a["title"],
            "revision": a["revision"],
            "body": "",
            "attributes": a["attributes"],
            "properties": {},
            "compact_context": True,
        }
        for a in model_pack["evidence"]
        if a["id"] in required and a["id"] not in {p["id"] for p in priority}
    ]
    priority += compact
    priority_ids = {a["id"] for a in priority}
    omitted = [a for a in model_pack["evidence"] if a["id"] not in priority_ids]
    facts = {
        **model_pack["facts"],
        "summarized_context_counts": dict(Counter(sources[a["id"]]["type"] for a in omitted)),
    }
    reduced = {"facts": facts, "evidence": priority}
    audit = {
        "reduced": True,
        "omitted_context_ids": [a["id"] for a in omitted],
        "original_tokens": token_size(model_pack),
        "excerpted_ids": [],
        "compact_context_ids": [a["id"] for a in compact],
        "injected_facts": facts,
    }
    # Preserve full narratives in the manifest; compact only the provider view.
    for limit in (512, 256, 128, 0):
        if token_size(reduced) <= budget:
            break
        reduced = {
            "facts": facts,
            "evidence": [
                {
                    "id": a["id"],
                    "title": a["title"],
                    "revision": a["revision"],
                    "body": a["body"][:limit],
                    **({"body_excerpt": True} if limit else {}),
                    "attributes": a["attributes"],
                    "properties": {
                        k: v
                        for k, v in a["properties"].items()
                        if k
                        in (
                            "Status",
                            "Severity",
                            "Outcome",
                            "Test case",
                            "Run",
                            "Listed as residual anomaly",
                        )
                    },
                }
                for a in priority
            ],
        }
        audit["excerpted_ids"] = [a["id"] for a in priority]
    audit["reduced_tokens"] = token_size(reduced)
    if audit["reduced_tokens"] > budget:
        raise EvidenceOverBudget(
            "Critical evidence and gap facts exceed the synthesis token budget"
        )
    return reduced, audit


def render_section(section: dict, pack: dict, claims: list[dict]) -> str:
    env = Environment(
        loader=FileSystemLoader("specs/templates"),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )

    nodes = {a["id"]: a for a in pack["evidence"]}

    def rev(value: str) -> str:
        return value[:8] if len(value) > 12 else value

    def cell(value: object) -> str:
        if isinstance(value, list):
            return "<br>".join(cell(v) for v in value) or "—"
        if isinstance(value, dict):
            return "; ".join(f"{k.replace('_', ' ')}: {cell(v)}" for k, v in value.items())
        text = str(value).replace("|", "\\|").replace("\n", "<br>")

        def link(match):
            id = match[0].rstrip(".")
            if id not in nodes:
                return match[0]
            a = nodes[id]
            label = id + (
                "@" + rev(a["source"]["revision"]) if a["source"]["system"] == "git" else ""
            )
            return f"[{label}]({a['source']['url']})" + match[0][len(id) :]

        return ID_PATTERN.sub(link, text)

    env.filters["revision"] = rev
    env.filters["cell"] = cell
    env.filters["claim_key"] = lambda c: sha(canonical(c))[:16]
    return env.get_template("section.md.j2").render(
        section=section,
        facts=pack["facts"],
        claims=claims,
        evidence={a["id"]: a for a in pack["evidence"]},
    )


def finish_section(
    section: dict,
    pack: dict,
    validated: list[dict],
    prompts: list[dict],
    failure: dict | None = None,
) -> dict:
    claims = list({canonical(c): c for response in validated for c in response["claims"]}.values())
    validation = {
        kind: [event for response in validated for event in response["validation"][kind]]
        for kind in ("rejected", "downgraded", "coerced", "normalized")
    }
    if section["mode"] == "ai":
        # Each chunk is validated against exactly its injected facts and evidence.
        # Enforce the global cap without revalidating against unreduced query facts.
        limit = section.get("max_claims", 6)
        validation["rejected"].extend(
            {"claim_index": index, "reason": "max_claims"} for index in range(limit, len(claims))
        )
        claims = claims[:limit]
    ids = (
        {a["id"] for a in pack["evidence"]}
        if section["mode"] == "deterministic" or section.get("columns")
        else {id for c in claims for id in c["citations"]}
    )
    rendered = render_section(
        {**section, **({"ai_unavailable": failure} if failure else {})}, pack, claims
    )
    counts = Counter(c["kind"] for c in claims)
    return {
        "id": section["id"],
        "title": section["title"],
        "mode": section["mode"],
        "query": section.get("query"),
        "entity": section.get("entity"),
        "query_fingerprint": fingerprint(pack),
        "facts": pack["facts"],
        "status": "ai_unavailable"
        if failure
        else ("human_input_required" if section["mode"] == "human" else "draft"),
        "ai_unavailable": failure,
        "cited_revisions": {
            a["id"]: a["source"]["revision"] for a in pack["evidence"] if a["id"] in ids
        },
        "claim_counts": {k: counts[k] for k in ("sourced", "inferred", "suggested")},
        "claims": claims,
        "validation": validation,
        "prompts": prompts,
        "markdown": rendered,
        "sha256": sha(rendered),
        "standard_refs": section.get("standard_refs", []),
    }


def section_pack(section: dict, graph: dict, params: dict) -> dict:
    return (
        query(
            graph,
            section["query"],
            {
                **params,
                **section.get("query_params", {}),
                **({"entity": section["entity"]} if "entity" in section else {}),
            },
        )
        if section["mode"] != "human"
        else {"facts": {}, "evidence": []}
    )


def prepare_ai(section: dict, pack: dict) -> tuple[dict, list[dict], dict]:
    """Pure section plan shared by generation, preview and folder batching."""
    prompt = load_prompt(section["prompt"])
    budget = (
        prompt["max_input_tokens"]
        - estimate_tokens(prompt["body"] + canonical(strict_claims_schema()))
        - 512
    )
    reduction = {"reduced": False}
    model_pack = prompt_pack(pack)
    if section.get("synthesis"):
        model_pack, reduction = reduce_synthesis(model_pack, pack, budget)
        chunks = [model_pack]
    else:
        chunks = partition_pack(model_pack, budget)
    for chunk in chunks:
        chunk["max_claims"] = section.get("max_claims", 6)
        chunk["preferred_kind"] = (
            "suggested" if section["allowed_kinds"] == ["suggested"] else "sourced"
        )
    return prompt, chunks, reduction


def generate_section(section: dict, graph: dict, params: dict, llm: LLM) -> dict:
    pack = section_pack(section, graph, params)
    responses = []
    prompts = []
    usage_sources = []
    tier = section.get("model_tier", "default")
    model = {"provider": llm.provider, "name": llm.model_for(tier), "tier": tier}
    if llm.provider == "copilotstudio":
        model["requested_tier"] = tier
        model["tier"] = "basic"
    if section["mode"] == "ai":
        prompt = load_prompt(section["prompt"])
        prompts = [{k: prompt[k] for k in ("id", "version", "sha256")}]
        try:
            prompt, chunks, reduction = prepare_ai(section, pack)
            for chunk in chunks:
                raw = llm.generate(
                    prompt["id"],
                    prompt["version"],
                    prompt["body"],
                    chunk,
                    prompt["max_output_tokens"],
                    model_tier=tier,
                )
                if llm.provider == "copilotstudio":
                    usage_sources.append(llm.last_usage_source)
                if llm.provider == "copilotstudio" and llm.last_model:
                    if model["name"] != llm.model_for(tier) and model["name"] != llm.last_model:
                        raise DraftingUnavailable("model_mismatch", "copilotstudio")
                    model["name"] = llm.last_model
                chunk_ids = {a["id"] for a in chunk["evidence"]}
                validation_pack = {
                    "facts": chunk["facts"],
                    "evidence": [a for a in pack["evidence"] if a["id"] in chunk_ids],
                }
                responses.append(validate_claims(raw, validation_pack, section["allowed_kinds"]))
        except DraftingUnavailable as exc:
            return {**finish_section(section, pack, [], prompts, exc.details), "model": model}
        except (BudgetExceeded, ValidationError, json.JSONDecodeError, ValueError) as exc:
            reason = (
                "budget_exceeded"
                if isinstance(exc, BudgetExceeded)
                else (
                    "evidence_over_budget"
                    if isinstance(exc, EvidenceOverBudget)
                    else "invalid_output"
                )
            )
            failure = DraftingUnavailable(reason, llm.provider, error_type=type(exc).__name__)
            failure.details["internal_message"] = (
                str(exc)
                if isinstance(exc, (BudgetExceeded, EvidenceOverBudget))
                else "Generated output failed local parsing or validation"
            )
            return {**finish_section(section, pack, [], prompts, failure.details), "model": model}
    result = {**finish_section(section, pack, responses, prompts), "model": model}
    if section["mode"] == "ai" and llm.provider == "copilotstudio":
        result["usage_source"] = combine_usage_sources(usage_sources)
    if section["mode"] == "ai":
        result["evidence_reduction"] = reduction
    return result


def assemble(spec: dict, graph: dict, params: dict, sections: list[dict], context: dict) -> dict:
    text = "# " + spec["title"] + "\n\n" + "\n".join(s["markdown"] for s in sections)
    validation = {
        k: [{"section": s["id"], **e} for s in sections for e in s["validation"][k]]
        for k in ("rejected", "downgraded", "coerced", "normalized")
    }
    prompts = {p["id"]: p for s in sections for p in s["prompts"]}
    manifest = {
        "doc_id": spec["id"],
        "doc_version": context["doc_version"],
        "generated_at": context["generated_at"],
        "generator_version": context["generator_version"],
        "template_spec": {
            "id": spec["id"],
            "version": spec["spec_version"],
            "sha256": context["template_sha256"],
        },
        "prompts": list(prompts.values()),
        "model": context["model"],
        "llm_cost_usd": context["llm_cost_usd"],
        **(
            {
                "copilot_credits": context["copilot_credits"],
                "usage_source": combine_usage_sources(
                    [
                        s.get("usage_source", "reported")
                        for s in sections
                        if s.get("model", {}).get("provider") == "copilotstudio"
                        and s["mode"] == "ai"
                        and s["status"] != "ai_unavailable"
                    ]
                ),
            }
            if "copilot_credits" in context
            else {}
        ),
        "source_snapshot": [
            {
                "artifact_id": a["id"],
                **{k: a["source"][k] for k in ("system", "native_id", "revision")},
                "content_hash": a["content_hash"],
            }
            for a in graph["artifacts"]
        ],
        "params": params,
        "sections": sections,
        "component_set": sorted(
            {
                a["id"]
                for a in graph["artifacts"]
                if a["type"] == "component"
                and any(a["id"] in s["cited_revisions"] for s in sections)
            }
        ),
        "component_names": {
            a["id"]: a["title"]
            for a in graph["artifacts"]
            if a["type"] == "component" and any(a["id"] in s["cited_revisions"] for s in sections)
        },
        "validation": validation,
        "document_sha256": sha(text),
        "review": {"pr_url": None, "reviewers": [], "status": "draft"},
        "telemetry": context["telemetry"],
    }
    return {"markdown": text, "manifest": manifest}


def generate_document(
    doc: str,
    graph: dict,
    params: dict,
    provider: str = "mock",
    out: Path = Path("out/documents"),
    llm: LLM | None = None,
) -> dict:
    spec = load_spec(doc)
    for key, definition in spec.get("params", {}).items():
        if definition.get("required") and not params.get(key):
            raise ValueError("Missing required parameter: " + key)
    llm = llm or LLM(provider)
    start = time.monotonic()
    initial_cost, initial_hits, initial_calls = llm.run_spend, llm.hits, llm.calls
    expanded = expand_sections(spec, graph)
    if llm.provider == "copilotstudio" and setting("DHF_COPILOT_MODE", "http") == "folder":
        jobs = []
        for section in expanded:
            if section["mode"] != "ai":
                continue
            try:
                prompt, chunks, _ = prepare_ai(section, section_pack(section, graph, params))
            except EvidenceOverBudget:
                continue  # The ordinary section path records its human placeholder.
            jobs.extend(
                (
                    prompt["id"],
                    prompt["version"],
                    prompt["body"],
                    chunk,
                    prompt["max_output_tokens"],
                    section.get("model_tier", "default"),
                )
                for chunk in chunks
            )
        llm.preload_copilot_folder(doc, jobs)
    sections = [generate_section(section, graph, params, llm) for section in expanded]
    version = (
        subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        or "uncommitted"
    )
    context = {
        "doc_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator_version": version,
        "template_sha256": sha(Path(f"specs/documents/{doc}.yaml").read_text()),
        "model": {
            "provider": llm.provider,
            "name": llm.last_model or llm.model,
            **({"tier": "basic"} if llm.provider == "copilotstudio" else {}),
        },
        "llm_cost_usd": 0 if llm.provider == "copilotstudio" else llm.run_spend - initial_cost,
        **(
            {"copilot_credits": llm.run_spend - initial_cost}
            if llm.provider == "copilotstudio"
            else {}
        ),
        "telemetry": {
            "seconds": time.monotonic() - start,
            "cache_hits": llm.hits - initial_hits,
            "calls": llm.calls - initial_calls,
        },
    }
    result = assemble(spec, graph, params, sections, context)
    if doc == "sfmea":
        from dhf.graph.reviews import risk_gaps

        result["manifest"]["risk_gaps"] = risk_gaps(
            graph, [c for s in sections for c in s["claims"]]
        )
    out.mkdir(parents=True, exist_ok=True)
    from dhf.render.diagram import write_diagrams

    result["manifest"]["diagrams"] = write_diagrams(doc, sections, out)
    from dhf.render import render_docx

    result["manifest"]["docx"] = render_docx(
        result["markdown"], out / (doc + ".docx"), timestamp=context["generated_at"]
    )
    result["manifest"]["docx"]["sha256"] = hashlib.sha256(
        (out / (doc + ".docx")).read_bytes()
    ).hexdigest()
    (out / (doc + ".md")).write_text(result["markdown"])
    (out / (doc + ".manifest.json")).write_text(json.dumps(result["manifest"], indent=2))
    return result
