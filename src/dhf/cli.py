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
    doc: str, release: str = "1.1", provider: str = "mock", db: str = "out/evidence.sqlite"
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
    result = generate_document(doc, graph, {"release": release}, provider)
    typer.echo(
        f"{doc}: {len(result['manifest']['sections'])} sections → out/documents/{doc}.md + manifest"
    )
    typer.echo(f"Validation: { {k: len(v) for k, v in result['manifest']['validation'].items()} }")


@app.command("generate-section")
def generate_section_command(
    doc: str,
    section: str,
    release: str = "1.1",
    provider: str = "mock",
    db: str = "out/evidence.sqlite",
) -> None:
    """Run one bounded section for the owner's cross-provider quality check."""
    import json
    from pathlib import Path

    from dhf.generate import generate_section, load_spec
    from dhf.graph import Store
    from dhf.llm import LLM

    spec = load_spec(doc)
    selected = next((s for s in spec["sections"] if s["id"] == section), None)
    if selected is None:
        raise typer.BadParameter("Unknown section")
    store = Store(Path(db))
    try:
        graph = store.graph()
    finally:
        store.close()
    if not graph["artifacts"]:
        raise typer.BadParameter("Ingest evidence first")
    llm = LLM(provider)
    result = generate_section(selected, graph, {"release": release}, llm)
    target = Path(f"out/cross-provider/{doc}-{section}-{provider}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2))
    typer.echo(f"{len(result['claims'])} validated claims; ${llm.run_spend:.6f} → {target}")
