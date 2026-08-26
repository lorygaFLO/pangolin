"""Implementation of the `pangolin restore` command."""

from __future__ import annotations

import typer

from pangolin.cli._discovery import (
    DEFAULT_PIPELINE,
    fail,
    load_pipelines,
    new_run_context,
    pipeline_steps,
    resolve_pipeline,
)

RESTORE_STEP = "restore_flow"


def restore(
    run_id: str = typer.Argument(..., help="Backup run_id to restore input data from."),
    pipeline: str = typer.Option(
        DEFAULT_PIPELINE,
        "--pipeline",
        "-p",
        help="Pipeline exposing the restore step.",
    ),
) -> None:
    """Restore input data from a backup run (shortcut for `pangolin step <pipeline> restore_flow <run_id>`)."""
    pipelines = load_pipelines()
    resolve_pipeline(pipeline, pipelines)

    steps = pipeline_steps(pipeline)
    if RESTORE_STEP not in steps:
        raise fail(f"Pipeline '{pipeline}' does not expose a '{RESTORE_STEP}' step.")

    ctx = new_run_context()
    steps[RESTORE_STEP](ctx, run_id)
