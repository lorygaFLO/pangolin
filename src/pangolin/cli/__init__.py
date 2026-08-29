"""Pangolin command-line interface (Typer application)."""

from __future__ import annotations

from typing import Optional

import typer

import pangolin
from pangolin.cli.bootstrap_cmd import bootstrap_app
from pangolin.cli.deploy_cmd import deploy
from pangolin.cli.init_cmd import init
from pangolin.cli.list_cmd import list_pipelines
from pangolin.cli.restore_cmd import restore
from pangolin.cli.run_cmd import run
from pangolin.cli.step_cmd import step


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(pangolin.__version__)
        raise typer.Exit()


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


@app.callback()
def _main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed pangolin version and exit.",
    ),
) -> None:
    return


def main() -> None:
    app()


if __name__ == "__main__":
    main()
