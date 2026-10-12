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
