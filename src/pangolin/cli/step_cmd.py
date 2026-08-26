"""Implementation of the `pangolin step` command."""

from __future__ import annotations

from typing import List, Optional

import typer

from pangolin.cli._discovery import (
    fail,
    load_pipelines,
    new_run_context,
    pipeline_steps,
    resolve_pipeline,
)


def step(
    pipeline: str = typer.Argument(..., help="Pipeline the step belongs to."),
    step_name: str = typer.Argument(..., metavar="STEP", help="Step (subflow) to run in isolation."),
    step_args: Optional[List[str]] = typer.Argument(
        None,
        metavar="[ARGS]...",
        help="Extra positional args forwarded to the step (e.g. restore_flow's run_id).",
    ),
) -> None:
    """Run a single step of a pipeline in isolation (use DEBUG=True in .env
    so RUN_ID is pinned and the step finds staging left by a previous run)."""
    pipelines = load_pipelines()
    resolve_pipeline(pipeline, pipelines)

    steps = pipeline_steps(pipeline)
    if not steps:
        raise fail(f"Pipeline '{pipeline}' has no debuggable steps.")
    if step_name not in steps:
        raise fail(
            f"Unknown step '{step_name}' for pipeline '{pipeline}'. "
            f"Available: {', '.join(steps)}"
        )

    ctx = new_run_context()
    steps[step_name](ctx, *(step_args or []))
