"""Implementation of the `pangolin list` command."""

from __future__ import annotations

import typer

from pangolin.cli._discovery import DEFAULT_PIPELINE, load_pipelines, pipeline_steps


def list_pipelines() -> None:
    """List available pipelines and their debuggable steps."""
    pipelines = load_pipelines()
    if not pipelines:
        typer.secho("No pipelines found in this project.", fg=typer.colors.YELLOW)
        return
    for name in pipelines:
        suffix = "  (default)" if name == DEFAULT_PIPELINE else ""
        typer.secho(f"{name}{suffix}", bold=True)
        for step_name in pipeline_steps(name):
            typer.echo(f"  - {step_name}")
