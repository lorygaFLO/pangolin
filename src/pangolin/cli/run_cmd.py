"""Implementation of the `pangolin run` command."""

from __future__ import annotations

from typing import Optional

import typer

from pangolin.cli._discovery import (
    DEFAULT_PIPELINE,
    fail,
    load_pipelines,
    resolve_pipeline,
)


def run(
    pipeline: Optional[str] = typer.Argument(
        None,
        help=f"Pipeline to run (default: '{DEFAULT_PIPELINE}', or the only one available).",
    ),
) -> None:
    """Run a pipeline of the current project."""
    pipelines = load_pipelines()
    if pipeline is None:
        if DEFAULT_PIPELINE in pipelines:
            pipeline = DEFAULT_PIPELINE
        elif len(pipelines) == 1:
            pipeline = next(iter(pipelines))
        else:
            raise fail(
                "No default pipeline found: specify one. "
                f"Available: {', '.join(pipelines) or '(none)'}"
            )
    resolve_pipeline(pipeline, pipelines)
    typer.secho(f"Running pipeline '{pipeline}'...", bold=True)
    pipelines[pipeline]()
