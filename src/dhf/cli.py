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
