import shutil
from pathlib import Path

import typer

from mock_ado.server import Server
from mock_ado.state import ROOT, apply_scenario, init

app = typer.Typer(help="Local synthetic Azure DevOps REST server.")


def reset_root(root: Path) -> None:
    resolved = root.resolve()
    # Never delete arbitrary locations; only our initialized test-tool state.
    if (
        not (resolved / "state.json").is_file()
        or not (resolved / "git/kestrel-device-sw.git").is_dir()
    ):
        raise ValueError("Refusing to reset a location without initialized mock state")
    shutil.rmtree(resolved)
    init(root)


@app.command("init")
def initialize(empty: bool = False, root: Path = ROOT) -> None:
    state = init(root, empty=empty)
    typer.echo(
        f"Mock initialized: {len(state['items'])} work items, "
        f"{len(state['runs'])} runs, {len(state['prs'])} PRs"
    )


@app.command()
def serve(port: int = 8089, root: Path = ROOT, empty: bool = False) -> None:
    server = Server(root=root, port=port, empty=empty)
    typer.echo(f"Mock ADO serving at http://localhost:{server.server_port}/kestrel-org")
    try:
        server.serve_forever()
    finally:
        server.server_close()


@app.command("apply-scenario")
def scenario(name: str) -> None:
    typer.echo(apply_scenario(name))


@app.command()
def reset() -> None:
    reset_root(ROOT)
    typer.echo("Mock reset to synthetic baseline")


@app.command("merge-docs-pr")
def merge_docs(pr_id: int) -> None:
    """Simulate the repo owner's merge, using test-tool authority on the mock only."""
    from mock_ado.state import merge_docs_pr

    typer.echo(merge_docs_pr(pr_id))
