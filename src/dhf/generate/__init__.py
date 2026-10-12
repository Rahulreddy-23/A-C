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

from dhf.generate.validator import ID_PATTERN, validate_claims
from dhf.graph.queries import fingerprint, query, stable_pack
from dhf.llm import LLM, BudgetExceeded, canonical
from dhf.llm.errors import DraftingUnavailable


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
    if meta["id"] != id or str(meta["version"]) != version or meta["output_schema"] != "claims.v1":
        raise ValueError("Prompt contract mismatch")
    return {**meta, "body": body.strip(), "sha256": sha(raw)}


def partition_pack(pack: dict, budget: int) -> list[dict]:
    """Conservative byte-based token bound; never silently discard evidence."""
    groups = []
    current = {"facts": pack["facts"], "evidence": []}
    if len(canonical(current).encode()) > budget:
        raise ValueError("Section facts exceed prompt budget; split the named query")
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
        if len(canonical(candidate).encode()) > budget:
            if not current["evidence"]:
                raise ValueError("Single artifact and context exceed prompt budget; split by unit")
            groups.append(current)
            current = {"facts": pack["facts"], "evidence": context(a)}
            if len(canonical(current).encode()) > budget:
                raise ValueError("Single artifact and context exceed prompt budget")
        else:
            current = candidate
        seen.update(item["id"] for item in current["evidence"])
    if current["evidence"] or not groups:
        groups.append(current)
    return groups


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
            return f"[{id}]({a['source']['url']})" + match[0][len(id) :]

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
        for kind in ("rejected", "downgraded", "coerced")
    }
    if section["mode"] == "ai":
        capped = validate_claims(
            {"claims": claims}, pack, section["allowed_kinds"], section.get("max_claims", 6)
        )
        validation["rejected"].extend(capped["validation"]["rejected"])
        claims = capped["claims"]
    ids = (
        {a["id"] for a in pack["evidence"]}
        if section["mode"] == "deterministic"
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


def generate_section(section: dict, graph: dict, params: dict, llm: LLM) -> dict:
    pack = (
        query(graph, section["query"], params)
        if section["mode"] != "human"
        else {"facts": {}, "evidence": []}
    )
    responses = []
    prompts = []
    if section["mode"] == "ai":
        prompt = load_prompt(section["prompt"])
        prompts = [{k: prompt[k] for k in ("id", "version", "sha256")}]
        budget = prompt["max_input_tokens"] - len(prompt["body"].encode())
        try:
            for chunk in partition_pack(stable_pack(pack), budget):
                chunk["max_claims"] = section.get("max_claims", 6)
                chunk["preferred_kind"] = (
                    "suggested" if section["allowed_kinds"] == ["suggested"] else "sourced"
                )
                raw = llm.generate(
                    prompt["id"],
                    prompt["version"],
                    prompt["body"],
                    chunk,
                    prompt["max_output_tokens"],
                )
                responses.append(validate_claims(raw, chunk, section["allowed_kinds"]))
        except DraftingUnavailable as exc:
            return finish_section(section, pack, [], prompts, exc.details)
        except (BudgetExceeded, ValidationError, json.JSONDecodeError, ValueError) as exc:
            reason = (
                "budget_exceeded" if isinstance(exc, BudgetExceeded) else "invalid_output_or_budget"
            )
            failure = DraftingUnavailable(reason, llm.provider, error_type=type(exc).__name__)
            return finish_section(section, pack, [], prompts, failure.details)
    return finish_section(section, pack, responses, prompts)


def assemble(spec: dict, graph: dict, params: dict, sections: list[dict], context: dict) -> dict:
    text = "# " + spec["title"] + "\n\n" + "\n".join(s["markdown"] for s in sections)
    validation = {
        k: [{"section": s["id"], **e} for s in sections for e in s["validation"][k]]
        for k in ("rejected", "downgraded", "coerced")
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
    sections = [generate_section(section, graph, params, llm) for section in spec["sections"]]
    version = (
        subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        or "uncommitted"
    )
    context = {
        "doc_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator_version": version,
        "template_sha256": sha(Path(f"specs/documents/{doc}.yaml").read_text()),
        "model": {"provider": provider, "name": llm.model},
        "llm_cost_usd": llm.run_spend - initial_cost,
        "telemetry": {
            "seconds": time.monotonic() - start,
            "cache_hits": llm.hits - initial_hits,
            "calls": llm.calls - initial_calls,
        },
    }
    result = assemble(spec, graph, params, sections, context)
    out.mkdir(parents=True, exist_ok=True)
    from dhf.render import render_docx

    result["manifest"]["docx"] = render_docx(
        result["markdown"], out / (doc + ".docx"), timestamp=context["generated_at"]
    )
    (out / (doc + ".md")).write_text(result["markdown"])
    (out / (doc + ".manifest.json")).write_text(json.dumps(result["manifest"], indent=2))
    return result
