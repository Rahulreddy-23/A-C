from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from dhf.llm import LLM

app = typer.Typer(
    help="Evidence-backed DHF drafts, traceability and review workflows.", no_args_is_help=True
)


@app.command()
def version() -> None:
    """Show the reference implementation version."""
    typer.echo("dhf 0.1.0")


@app.callback()
def main() -> None:
    """DHF evidence automation."""


@app.command()
def ingest(source: str = "ado", db: str = "out/evidence.sqlite", verbose: bool = False) -> None:
    """Ingest ADO over HTTP or synthetic fixture files with provenance."""
    from pathlib import Path

    from dhf.graph import Store
    from dhf.ingest.ado import ADO
    from dhf.ingest.fixtures import ingest_fixtures

    if source == "fixtures":
        data = ingest_fixtures()
    elif source == "ado":
        adapter = ADO()
        try:
            data = adapter.ingest()
        finally:
            adapter.close()
        mode = "read-only" if adapter.read_only else "docs-repo writes enabled"
        scope = (
            f"{len(adapter.scope.get('seed_ids', []))} seed items"
            if adapter.scope
            else "whole project"
        )
        typer.echo(f"ADO {adapter.project} ({mode}, {scope})")
        for key, count in sorted(adapter.report.items()):
            typer.echo(f"  {key}: {count}")
    else:
        raise typer.BadParameter("source must be ado or fixtures")
    store = Store(Path(db))
    try:
        import json
        from collections import Counter

        previous = {a["id"]: a for a in store.graph()["artifacts"]}
        nodes = {a["id"]: a for a in data["artifacts"]}
        result = store.ingest(data)
        typer.echo(
            f"Snapshot {result['snapshot']}: {result['artifacts']} artifacts, "
            f"{result['links']} links"
        )
        for kind in ("added", "changed", "removed"):
            counts = Counter((nodes.get(id) or previous[id])["type"] for id in result[kind])
            typer.echo(
                f"{kind}: {len(result[kind])} "
                + ", ".join(f"{type}={count}" for type, count in sorted(counts.items()))
            )
        if result["changed"]:
            typer.echo(
                "Changed IDs: "
                + ", ".join(result["changed"][:20])
                + (" … (use --verbose)" if len(result["changed"]) > 20 else "")
            )
        if verbose:
            typer.echo(json.dumps(result, indent=2))
    finally:
        store.close()


@app.command("gaps")
def gaps_command(db: str = "out/evidence.sqlite", output_dir: str = "out") -> None:
    """Write deterministic gap findings and trace coverage as Markdown and JSON."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.trace import coverage, gaps, unassessable_rules
    from dhf.trace.reports import gap_rules, gaps_markdown

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence first")
    findings = gaps(graph)
    blind = unassessable_rules(graph, gap_rules())
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "gaps.json").write_text(
        json.dumps(
            {"findings": findings, "coverage": coverage(graph), "not_assessable": blind}, indent=2
        )
    )
    (out / "gaps.md").write_text(gaps_markdown(findings, gap_rules(), blind))
    shown = sum(f["rule"] not in blind for f in findings)
    typer.echo(
        f"{shown} deterministic gaps"
        + (f" ({len(blind)} rules not assessable from these sources)" if blind else "")
        + f" → {out / 'gaps.md'} + {out / 'gaps.json'}"
    )


@app.command("import-docs")
def import_docs_command(
    folder: str,
    profile: str = "specs/doc_import/dhf_documents.yaml",
    db: str = "out/docs/evidence.sqlite",
    output_dir: str = "out/docs",
) -> None:
    """Import existing DHF documents and ADO CSV exports as a local evidence baseline."""
    import json
    from pathlib import Path

    import yaml

    from dhf.graph import Store
    from dhf.ingest.documents import import_folder
    from dhf.trace import evaluate_rules
    from dhf.trace.reports import import_markdown

    graph, summary = import_folder(Path(folder), Path(profile))
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    store = Store(Path(db))
    try:
        result = store.ingest(graph)
    finally:
        store.close()
    rules = yaml.safe_load(Path("specs/rules/document_baseline.yaml").read_text())["rules"]
    findings = evaluate_rules(graph, rules)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "import-report.json").write_text(
        json.dumps({"summary": summary, "findings": findings}, indent=2)
    )
    (out / "import-report.md").write_text(import_markdown(summary, findings, rules, graph))
    typer.echo(
        f"Snapshot {result['snapshot']}: "
        + ", ".join(f"{k}={v}" for k, v in summary["artifact_counts"].items())
        + f", links={len(graph['links'])}"
    )
    typer.echo(f"{len(findings)} baseline findings → {out / 'import-report.md'}")


@app.command("rtm")
def rtm_command(
    release: str = "1.1", db: str = "out/evidence.sqlite", output_dir: str = "out"
) -> None:
    """Write requirement → component/code/test/latest-result trace rows."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.trace import rtm
    from dhf.trace.reports import rtm_markdown

    store = Store(Path(db))
    try:
        graph = store.graph()
        rows = rtm(graph, release)
    finally:
        store.close()
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rtm.json").write_text(json.dumps(rows, indent=2))
    (out / "rtm.md").write_text(rtm_markdown(graph, rows))
    typer.echo(f"{len(rows)} RTM rows → {out / 'rtm.md'} + {out / 'rtm.json'}")


@app.command()
def generate(
    doc: str,
    release: str = "1.1",
    provider: str = "mock",
    db: str = "out/evidence.sqlite",
    open_pr: bool = False,
    debug: bool = False,
    input_file: str | None = None,
    since: int | None = None,
    documents: str = "out/documents",
    impact_file: str | None = None,
) -> None:
    """Generate a typed, cited DHF draft from its YAML document specification."""
    from pathlib import Path

    from dhf.generate import generate_document
    from dhf.graph import Store

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence first")
    params = {"release": release}
    if input_file:
        import json

        params["review_input"] = json.loads(Path(input_file).read_text())
    if doc == "drr":
        import json

        params["documents"] = [
            json.loads(p.read_text()) for p in Path(documents).glob("*.manifest.json")
        ]
        from dhf.ingest.ado import ADO
        from dhf.review import DocsReview

        ado = ADO()
        try:
            params["documents"] += DocsReview(ado).approved_documents()
        finally:
            ado.close()
        if since is not None:
            params["baseline_snapshot"] = since
            prior = Store(Path(db))
            try:
                params["previous_snapshot"] = prior.graph(since)
            finally:
                prior.close()
        if impact_file:
            params["impact_reports"] = json.loads(Path(impact_file).read_text())
    from dhf.llm import LLM

    llm = LLM(provider)
    result = generate_document(doc, graph, params, provider, out=Path(documents), llm=llm)
    report_budget(llm)
    report_drafting_failures(result["manifest"]["sections"], debug)
    typer.echo(
        f"{doc}: {len(result['manifest']['sections'])} sections → {documents}/{doc}.md + manifest"
    )
    typer.echo(f"Validation: { {k: len(v) for k, v in result['manifest']['validation'].items()} }")
    if open_pr:
        import json

        from dhf.ingest.ado import ADO
        from dhf.review import DocsReview
        from dhf.trace import gaps

        ado = ADO()
        try:
            review = DocsReview(ado)
            published = review.publish(result, gap_count=len(gaps(graph)))
            Path(documents, doc + ".docx").write_bytes((review.root / (doc + ".docx")).read_bytes())
            Path(documents, doc + ".manifest.json").write_text(
                json.dumps(result["manifest"], indent=2)
            )
            typer.echo(f"PR {published['pr_id']}: {published['pr_url']}")
            typer.echo(f"Readiness: {len(published['readiness']['blockers'])} blockers")
        finally:
            ado.close()


@app.command("copilot-request")
def copilot_request(
    doc: str,
    section: str,
    release: str = "1.1",
    db: str = "out/evidence.sqlite",
) -> None:
    """Print an exact section request for the tenant prompt builder; send nothing."""
    import json
    from pathlib import Path

    from dhf.generate import expand_sections, load_spec, prepare_ai, section_pack
    from dhf.graph import Store
    from dhf.llm import LLM

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence first")
    matches = [
        item
        for item in expand_sections(load_spec(doc), graph)
        if item["id"] == section and item["mode"] == "ai"
    ]
    if len(matches) != 1:
        raise typer.BadParameter("Choose one AI section ID from the document spec")
    item = matches[0]
    prompt, chunks, _ = prepare_ai(item, section_pack(item, graph, {"release": release}))
    if len(chunks) != 1:
        raise typer.BadParameter(
            "Section needs multiple evidence chunks; choose a single-chunk section"
        )
    llm = LLM("copilotstudio")
    typer.echo(
        json.dumps(
            llm.copilot_request(
                prompt["id"],
                prompt["version"],
                prompt["body"],
                chunks[0],
                prompt["max_output_tokens"],
                model_tier=item.get("model_tier", "default"),
            ),
            indent=2,
            ensure_ascii=False,
        )
    )


def report_budget(llm: "LLM") -> None:
    if llm.provider != "mock":
        budget = llm.budget_status()
        if llm.provider == "copilotstudio":
            typer.echo(
                f"copilotstudio local headroom: {budget['remaining_credits']:.3f} credits "
                f"of {budget['hard_cap_credits']:.1f} cap "
                f"(actual {budget['actual_credits']:.3f}, "
                f"reserved {budget['reserved_credits']:.3f}); check tenant Monitor"
            )
            return
        typer.echo(
            f"{budget['provider']} cumulative headroom: ${budget['remaining_usd']:.6f} "
            f"of ${budget['hard_cap_usd']:.2f} hard cap "
            f"(actual ${budget['actual_usd']:.6f}, reserved ${budget['reserved_usd']:.6f})"
        )


def report_drafting_failures(sections: list[dict], debug: bool = False) -> None:
    """Print only sanitized failure metadata; SDK messages never reach Rich tracebacks."""
    import json

    for section in sections:
        error = section.get("ai_unavailable")
        if not error:
            continue
        typer.echo(
            f"{error['provider']}: section={section['id']} reason={error['reason']} "
            f"http={error.get('http_status') or 'n/a'} "
            f"type={error.get('error_type') or 'n/a'} "
            f"request={error.get('request_id') or 'n/a'}"
        )
        if debug:
            typer.echo(json.dumps(error, indent=2))


@app.command("generate-section")
def generate_section_command(
    doc: str,
    section: str,
    release: str = "1.1",
    provider: str = "mock",
    db: str = "out/evidence.sqlite",
    debug: bool = False,
) -> None:
    """Run one bounded section for the owner's cross-provider quality check."""
    import json
    from pathlib import Path

    from dhf.generate import expand_sections, generate_section, load_spec
    from dhf.graph import Store
    from dhf.llm import LLM

    spec = load_spec(doc)
    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence first")
    selected = next((s for s in expand_sections(spec, graph) if s["id"] == section), None)
    if selected is None:
        raise typer.BadParameter("Unknown section")
    llm = LLM(provider)
    result = generate_section(selected, graph, {"release": release}, llm)
    report_drafting_failures([result], debug)
    report_budget(llm)
    target = Path(f"out/cross-provider/{doc}-{section}-{provider}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    typer.echo(f"{len(result['claims'])} validated claims; ${llm.run_spend:.6f} → {target}")


@app.command("check")
def check_command(doc: str, pr_id: int | None = None) -> None:
    """Recheck edited Markdown; with --pr-id, push updated manifest/DOCX and PR status."""
    import json
    from pathlib import Path

    from dhf.ingest.ado import ADO
    from dhf.review import DocsReview, readiness

    if pr_id is None:
        root = Path("out/documents")
        result = readiness(
            (root / (doc + ".md")).read_text(),
            json.loads((root / (doc + ".manifest.json")).read_text()),
        )
    else:
        ado = ADO()
        try:
            result = DocsReview(ado).check_pr(doc, pr_id)
        finally:
            ado.close()
    typer.echo(json.dumps(result, indent=2))
    if not result["ready"]:
        raise typer.Exit(1)


@app.command("baseline")
def baseline_command(doc: str, pr_id: int = typer.Option(...)) -> None:
    """Tag a ready document after its PR was merged by a human."""
    from dhf.ingest.ado import ADO
    from dhf.review import DocsReview

    ado = ADO()
    try:
        typer.echo(DocsReview(ado).create_baseline(doc, pr_id))
    finally:
        ado.close()


@app.command("consistency")
def consistency_command(
    db: str = "out/evidence.sqlite", documents: str = "out/documents", baselines: bool = True
) -> None:
    """Check source and document component sets; emit reviewable findings."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.trace.consistency import consistency

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    manifests = [json.loads(p.read_text()) for p in sorted(Path(documents).glob("*.manifest.json"))]
    if baselines:
        from dhf.ingest.ado import ADO
        from dhf.review import DocsReview

        ado = ADO()
        try:
            manifests += DocsReview(ado).approved_documents()
        finally:
            ado.close()
    findings = consistency(graph, manifests)
    Path("out/consistency.json").write_text(json.dumps(findings, indent=2))
    typer.echo(f"{len(findings)} consistency findings → out/consistency.json")


def document_impacts(db: str, documents: str, since: str = "baseline") -> tuple[dict, list[dict]]:
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.impact import impact, write_report

    store = Store(Path(db))
    try:
        graph = store.graph()
        previous = None
        if since != "baseline":
            if since.isdigit():
                previous = store.graph(int(since))
            else:
                row = store.db.execute(
                    "SELECT id FROM snapshots WHERE at<=? ORDER BY id DESC LIMIT 1", (since,)
                ).fetchone()
                if not row:
                    raise typer.BadParameter("No snapshot at or before timestamp")
                previous = store.graph(row[0])
            if not previous["artifacts"]:
                raise typer.BadParameter("Unknown snapshot")
        reports = []
        for path in sorted(Path(documents).glob("*.manifest.json")):
            manifest = json.loads(path.read_text())
            report = impact(graph, manifest, previous)
            statuses = {s["id"]: s["status"] for s in report["sections"]}
            for section in manifest["sections"]:
                section["evidence_status"] = statuses.get(section["id"], "current")
            manifest["impact"] = report
            path.write_text(json.dumps(manifest, indent=2))
            reports.append(report)
        write_report(reports)
        return graph, reports
    finally:
        store.close()


@app.command("impact")
def impact_command(
    since: str = "baseline", db: str = "out/evidence.sqlite", documents: str = "out/documents"
) -> None:
    """Compare current evidence with document source baselines or an ingest timestamp."""
    _, reports = document_impacts(db, documents, since)
    for report in reports:
        for status in ("stale", "possibly_affected"):
            typer.echo(
                f"{report['document']}: "
                f"{sum(s['status'] == status for s in report['sections'])} {status}"
            )
    typer.echo("Impact → out/impact.md + out/impact.json")


@app.command("regenerate")
def regenerate_command(
    stale: bool = typer.Option(False, "--stale"),
    db: str = "out/evidence.sqlite",
    documents: str = "out/documents",
    open_pr: bool = False,
) -> None:
    """Regenerate directly stale sections, preserving all other edited section bytes."""
    import json
    from pathlib import Path

    from dhf.impact import regenerate
    from dhf.ingest.ado import ADO
    from dhf.review import DocsReview
    from dhf.trace import gaps

    if not stale:
        raise typer.BadParameter("Specify --stale")
    graph, reports = document_impacts(db, documents)
    root = Path(documents)
    from dhf.llm import LLM

    llms: dict[str, LLM] = {}
    for report in reports:
        changed = [s["id"] for s in report["sections"] if s["status"] == "stale"]
        if not changed:
            continue
        doc = report["document"]
        manifest = json.loads((root / (doc + ".manifest.json")).read_text())
        provider = manifest["model"]["provider"]
        if provider not in llms:
            llms[provider] = LLM(provider)
        result = regenerate(
            graph, manifest, (root / (doc + ".md")).read_text(), report, root, llms[provider]
        )
        report_budget(llms[provider])
        typer.echo(f"{doc}: regenerated {len(changed)} sections")
        if open_pr:
            ado = ADO()
            try:
                published = DocsReview(ado).publish(
                    result, changed_sections=changed, gap_count=len(gaps(graph))
                )
                (root / (doc + ".manifest.json")).write_text(
                    json.dumps(result["manifest"], indent=2)
                )
                (root / (doc + ".docx")).write_bytes(
                    (DocsReview(ado).root / (doc + ".docx")).read_bytes()
                )
                typer.echo(f"PR {published['pr_id']}: {published['pr_url']}")
            finally:
                ado.close()


@app.command("watch")
def watch_command(
    interval: float = 60,
    cycles: int | None = None,
    db: str = "out/evidence.sqlite",
    documents: str = "out/documents",
    regenerate_stale: bool = False,
    open_pr: bool = False,
) -> None:
    """Poll native ADO evidence; optional finite cycles support demonstrations."""
    import time
    from pathlib import Path

    from dhf.graph import Store
    from dhf.ingest.ado import ADO

    if interval < 0 or (cycles is not None and cycles < 1):
        raise typer.BadParameter("interval must be nonnegative; cycles must be positive")
    count = 0
    try:
        while cycles is None or count < cycles:
            ado = ADO()
            store = Store(Path(db))
            try:
                delta = store.ingest(ado.ingest())
            finally:
                ado.close()
                store.close()
            count += 1
            if delta["changed"] or delta["added"] or delta["removed"]:
                typer.echo(
                    f"Changed evidence: {len(delta['changed'])} changed, "
                    f"{len(delta['added'])} added, {len(delta['removed'])} removed"
                )
                impact_command(db=db, documents=documents)
                if regenerate_stale:
                    regenerate_command(stale=True, db=db, documents=documents, open_pr=open_pr)
            else:
                typer.echo("Evidence unchanged")
            if cycles is None or count < cycles:
                time.sleep(interval)
    except KeyboardInterrupt:
        typer.echo("Watch stopped")


@app.command("propose")
def propose_command(
    db: str = "out/evidence.sqlite", documents: str = "out/documents", provider: str = "mock"
) -> None:
    """Draft L01–L03 review proposals locally, without source writes."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.llm import LLM
    from dhf.propose import propose

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    manifests = [json.loads(p.read_text()) for p in Path(documents).glob("*.manifest.json")]
    llm = LLM(provider)
    result = propose(graph, manifests, llm=llm)
    report_budget(llm)
    typer.echo(f"{len(result['sections'])} proposal checks → out/proposals/proposals.md + JSON")


@app.command("eval")
def eval_command(
    db: str = "out/evidence.sqlite",
    documents: str = "out/documents",
    impact_file: str | None = None,
    baseline_snapshot: int = 1,
) -> None:
    """Score synthetic baseline goldens and saved pre-regeneration change impact."""
    import json
    from pathlib import Path

    from dhf.evaluation import clause_markdown, evaluate, metrics_markdown
    from dhf.graph import Store

    root = Path(documents)
    manifests = [json.loads(p.read_text()) for p in sorted(root.glob("*.manifest.json"))]
    if not manifests:
        raise typer.BadParameter("Generate documents first")
    store = Store(Path(db))
    try:
        graph, baseline = store.graph(), store.graph(baseline_snapshot)
    finally:
        store.close()
    if not baseline["artifacts"]:
        raise typer.BadParameter("Unknown baseline snapshot")
    reports = json.loads(Path(impact_file).read_text()) if impact_file else None
    result = evaluate(
        graph,
        baseline,
        manifests,
        {d["doc_id"]: (root / (d["doc_id"] + ".md")).read_text() for d in manifests},
        reports,
    )
    Path("out").mkdir(exist_ok=True)
    Path("out/metrics.json").write_text(json.dumps(result, indent=2))
    Path("out/metrics.md").write_text(metrics_markdown(result))
    Path("out/clause_coverage.md").write_text(clause_markdown(result["clause_coverage"]))
    typer.echo(
        f"Unknown IDs: {result['unknown_id_count']}; "
        f"gaps precision={result['gap_detection']['precision']:.2f} "
        f"recall={result['gap_detection']['recall']:.2f}"
    )
    typer.echo("Metrics → out/metrics.md + JSON; clause appendix → out/clause_coverage.md")
    if (
        result["unknown_ids"]
        or result["schema_errors"]
        or any(d["mismatches"] for d in result["deterministic_goldens"].values())
    ):
        raise typer.Exit(1)


@app.command("audit-pack")
def audit_pack_command(
    release: str = "1.1",
    db: str = "out/evidence.sqlite",
    documents: str = "out/documents",
    output: str = "out/audit-pack.zip",
) -> None:
    """Export draft documents, provenance snapshots, trace reports and checked hashes."""
    from pathlib import Path

    from dhf.graph import Store
    from dhf.review.audit import audit_pack

    store = Store(Path(db))
    try:
        snapshots = [
            store.graph(row[0])
            for row in store.db.execute("SELECT id FROM snapshots ORDER BY id").fetchall()
        ]
    finally:
        store.close()
    result = audit_pack(snapshots, Path(documents), Path(output), release)
    typer.echo(f"Audit pack: {result['verified_files']} verified files → {output}")


@app.command("discover")
def discover_command(output: str = "out/discovery/ado_mapping.yaml") -> None:
    """Inspect native ADO evidence and save a mapping draft for human confirmation."""
    import json
    from pathlib import Path

    import yaml

    from dhf.ingest.ado import ADO
    from dhf.ingest.discovery import discover

    ado = ADO()
    try:
        report = discover(ado)
    finally:
        ado.close()
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(report["mapping"], sort_keys=False))
    target.with_suffix(".discovery.json").write_text(json.dumps(report, indent=2))
    typer.echo(f"Mapping draft → {target}; {len(report['unknowns'])} unknowns require confirmation")


@app.command("verify-support")
def verify_support_command(
    doc: str | None = None,
    sample: int = 5,
    provider: str = "mock",
    db: str = "out/evidence.sqlite",
    documents: str = "out/documents",
) -> None:
    """Assess sourced/inferred claims; flags and Word comments are advisory only."""
    import hashlib
    import json
    from pathlib import Path

    from dhf.generate.support import support_comments, verify_document
    from dhf.graph import Store
    from dhf.llm import LLM
    from dhf.render import render_docx

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    root = Path(documents)
    paths = sorted(root.glob("*.manifest.json"))
    if doc:
        paths = [p for p in paths if p.name == doc + ".manifest.json"]
    if not paths:
        raise typer.BadParameter("No matching documents")
    llm = LLM(provider)
    for path in paths:
        manifest = verify_document(graph, json.loads(path.read_text()), llm, sample)
        id = manifest["doc_id"]
        word = root / (id + ".docx")
        manifest["docx"] = render_docx(
            (root / (id + ".md")).read_text(),
            word,
            timestamp=manifest["generated_at"],
            support_findings=support_comments(manifest),
        )
        manifest["docx"]["sha256"] = hashlib.sha256(word.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest, indent=2))
        report = manifest["claim_support"]
        typer.echo(
            f"{id}: {report['counts']}; support rate={report['support_rate']} "
            f"among {report['support_rate_denominator']} verdicts; coverage "
            f"{report['coverage']['verified']}/{report['coverage']['sampled_eligible']} "
            "sampled eligible "
            f"({report['coverage']['document_eligible']} in document); "
            f"{report['rationale_unverified_count']} rationales unverified; advisory only"
        )
    report_budget(llm)


@app.command("explore")
def explore_command(
    db: str = "out/evidence.sqlite",
    documents: str = "out/documents",
    output: str = "out/explorer.html",
    impact_file: str | None = None,
    baseline_file: str | None = None,
) -> None:
    """Write one offline HTML explorer with provenance, G/C/F gaps and stale sections."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.render.explorer import create_explorer

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence before exploring")
    manifests = [json.loads(p.read_text()) for p in sorted(Path(documents).glob("*.manifest.json"))]
    reports = json.loads(Path(impact_file).read_text()) if impact_file else None
    from dhf.trace.consistency import legacy_design

    baselines = [legacy_design(Path(baseline_file).read_text())] if baseline_file else []
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(create_explorer(graph, manifests, reports, baselines))
    typer.echo(f"Explorer: {len(graph['artifacts'])} artifacts → {target}; offline HTML")


@app.command("export-snapshot")
def export_snapshot_command(
    db: str = "out/evidence.sqlite", output_dir: str = "out/snapshot-export"
) -> None:
    """Write a local canonical JSON/CSV evidence package for reviewed import."""
    from pathlib import Path

    from dhf.graph import Store
    from dhf.graph.export import snapshot_files

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence before exporting")
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    for name, content in snapshot_files(graph).items():
        (target / name).write_text(content)
    typer.echo(
        f"Snapshot export: {len(graph['artifacts'])} artifacts, {len(graph['links'])} links"
        f" → {target}; review before upload"
    )
