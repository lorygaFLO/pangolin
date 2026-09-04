"""Discovery helpers: load pipelines/steps from the user's project (cwd).

The CLI runs inside a project scaffolded by `pangolin init`: the project root
(current working directory) contains the `pipelines/` package and `config/`.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import typer

from pangolin.cli._prefect_env import bootstrap_prefect_home

DEFAULT_PIPELINE = "full_processing"


def fail(message: str) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=True)
    return typer.Exit(code=1)


def _project_root() -> Path:
    root = Path.cwd().resolve()
    if not (root / "pipelines" / "__init__.py").is_file():
        raise fail(
            f"No pipelines/ package found in '{root}'. "
            "Run this command from a pangolin project root (see `pangolin init`)."
        )
    return root


def load_pipelines() -> dict:
    """Import the project's pipelines package and return its PIPELINES dict."""
    bootstrap_prefect_home()
    root = _project_root()
    os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    pipelines_pkg = importlib.import_module("pipelines")
    return dict(pipelines_pkg.PIPELINES)


def resolve_pipeline(name: str, pipelines: dict) -> str:
    if name not in pipelines:
        raise fail(
            f"Unknown pipeline '{name}'. Available: {', '.join(pipelines) or '(none)'}"
        )
    return name


def pipeline_steps(pipeline_name: str) -> dict:
    """Auto-discover a pipeline's internal subflows (any module-level @flow
    that isn't the pipeline's own PIPELINE flow)."""
    from prefect.flows import Flow

    module = importlib.import_module(f"pipelines.{pipeline_name}")
    main_flow = getattr(module, "PIPELINE", None)
    return {
        name: obj
        for name, obj in vars(module).items()
        if isinstance(obj, Flow) and obj is not main_flow
    }


def new_run_context():
    """Instantiate a RunContext (needed to run a step standalone).

    Uses `get_run_context()` so the project's `custom/run_context.py`
    subclass (if any) is honored here too, not just in the pipeline.
    """
    from pangolin.config.run_context import get_run_context

    return get_run_context()
