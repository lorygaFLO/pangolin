"""Pangolin command-line interface (Typer application)."""

from __future__ import annotations

import typer

import pangolin
from pangolin.cli.bootstrap_cmd import bootstrap_app
from pangolin.cli.deploy_cmd import deploy
from pangolin.cli.init_cmd import init
from pangolin.cli.list_cmd import list_pipelines
from pangolin.cli.restore_cmd import restore
from pangolin.cli.run_cmd import run
from pangolin.cli.step_cmd import step

app = typer.Typer(
    name="pangolin",
    help="Pangolin: traceable, config-driven data processing pipelines.",
    no_args_is_help=True,
)

app.command("init")(init)
app.command("run")(run)
app.command("list")(list_pipelines)
app.command("step")(step)
app.command("restore")(restore)
app.command("deploy")(deploy)
app.add_typer(bootstrap_app, name="bootstrap")


@app.command("version")
def version() -> None:
    """Show the installed pangolin version."""
    typer.echo(pangolin.__version__)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
