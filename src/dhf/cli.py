import typer

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
def gaps_command(db: str = "out/evidence.sqlite") -> None:
    """Write deterministic gap findings and trace coverage as Markdown and JSON."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.trace import coverage, gaps

    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence first")
    findings = gaps(graph)
    out = Path("out")
    out.mkdir(exist_ok=True)
    (out / "gaps.json").write_text(
        json.dumps({"findings": findings, "coverage": coverage(graph)}, indent=2)
    )
    from collections import Counter

    import yaml

    counts = Counter(f["rule"] for f in findings)
    rules = yaml.safe_load(Path("specs/rules/gaps.yaml").read_text())["rules"]
    summary = (
        "# Evidence gaps\n\n| Rule | Count | Why it matters | Recommended action |\n"
        "|---|---:|---|---|\n"
    )
    summary += "".join(
        f"| {r['id']} | {counts[r['id']]} | {r['title']} | {r['action']} |\n" for r in rules
    )
    detail = "\n| Rule | Artifact revision | Finding | Recommended action |\n|---|---|---|---|\n"
    detail += "".join(
        f"| {f['rule']} | [{f['artifact_id']}@r{f['revision']}]({f['source_url']}) | "
        f"{f['message']} | {f['action']} |\n"
        for f in findings
    )
    (out / "gaps.md").write_text(summary + detail)
    typer.echo(f"{len(findings)} deterministic gaps → out/gaps.md + out/gaps.json")


@app.command("rtm")
def rtm_command(release: str = "1.1", db: str = "out/evidence.sqlite") -> None:
    """Write requirement → component/code/test/latest-result trace rows."""
    import json
    from pathlib import Path

    from dhf.graph import Store
    from dhf.trace import rtm

    store = Store(Path(db))
    try:
        graph = store.graph()
        rows = rtm(graph, release)
    finally:
        store.close()
    Path("out/rtm.json").write_text(json.dumps(rows, indent=2))
    nodes = {a["id"]: a for a in graph["artifacts"]}

    def citation(id: str) -> str:
        return f"[{id}]({nodes[id]['source']['url']})"

    text = (
        "# Requirement trace matrix\n\n"
        "| Requirement | Rev | Components | Units | Changes | Tests | Latest results |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    for r in rows:
        cells = [citation(r["requirement"]), r["revision"]]
        cells += [
            ", ".join(citation(id) for id in r[key])
            for key in ("components", "units", "changes", "tests")
        ]
        cells += [", ".join(citation(v["result"]) + ": " + v["outcome"] for v in r["results"])]
        text += "| " + " | ".join(cells) + " |\n"
    Path("out/rtm.md").write_text(text)
    typer.echo(f"{len(rows)} RTM rows → out/rtm.md + out/rtm.json")


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
            json.loads(p.read_text()) for p in Path("out/documents").glob("*.manifest.json")
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
        if Path("out/impact.json").exists():
            params["impact_reports"] = json.loads(Path("out/impact.json").read_text())
    result = generate_document(doc, graph, params, provider)
    report_drafting_failures(result["manifest"]["sections"], debug)
    typer.echo(
        f"{doc}: {len(result['manifest']['sections'])} sections → out/documents/{doc}.md + manifest"
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
            Path(f"out/documents/{doc}.docx").write_bytes(
                (review.root / (doc + ".docx")).read_bytes()
            )
            Path(f"out/documents/{doc}.manifest.json").write_text(
                json.dumps(result["manifest"], indent=2)
            )
            typer.echo(f"PR {published['pr_id']}: {published['pr_url']}")
            typer.echo(f"Readiness: {len(published['readiness']['blockers'])} blockers")
        finally:
            ado.close()


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
    for report in reports:
        changed = [s["id"] for s in report["sections"] if s["status"] == "stale"]
        if not changed:
            continue
        doc = report["document"]
        manifest = json.loads((root / (doc + ".manifest.json")).read_text())
        result = regenerate(graph, manifest, (root / (doc + ".md")).read_text(), report, root)
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
    result = propose(graph, manifests, llm=LLM(provider))
    typer.echo(f"{len(result['sections'])} proposal checks → out/proposals/proposals.md + JSON")
