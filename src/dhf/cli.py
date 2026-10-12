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
def ingest(source: str = "ado", db: str = "out/evidence.sqlite") -> None:
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
        typer.echo(store.ingest(data))
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
    (out / "gaps.md").write_text(
        "# Evidence gaps\n\n| Rule | Artifact | Finding |\n|---|---|---|\n"
        + "".join(
            f"| {f['rule']} | [{f['artifact_id']}]({f['source_url']}) | {f['message']} |\n"
            for f in findings
        )
    )
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
        rows = rtm(store.graph(), release)
    finally:
        store.close()
    Path("out/rtm.json").write_text(json.dumps(rows, indent=2))
    Path("out/rtm.md").write_text(
        "# Requirement trace matrix\n\n"
        "| Requirement | Components | Changes | Tests | Outcomes |\n|---|---|---|---|---|\n"
        + "".join(
            "| "
            + " | ".join(
                [
                    r["requirement"],
                    ", ".join(r["components"]),
                    ", ".join(r["changes"]),
                    ", ".join(r["tests"]),
                    ", ".join(v["outcome"] for v in r["results"]),
                ]
            )
            + " |\n"
            for r in rows
        )
    )
    typer.echo(f"{len(rows)} RTM rows → out/rtm.md + out/rtm.json")
