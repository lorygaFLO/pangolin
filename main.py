"""
Main entry point for the data processing pipeline using Prefect.

Pipelines are auto-discovered from the pipelines/ folder — each file there
defines one @flow (see pipelines/__init__.py for the discovery rules).

Usage:
    python main.py                     # run the default pipeline (full_processing)
    python main.py --pipeline <name>   # run a specific pipeline by name
    python main.py --list-pipelines    # list all available pipeline names
    python main.py --generate          # shorthand for --pipeline generate_test_data
    python main.py --pipeline <name> --list-steps    # list debuggable steps of a pipeline
    python main.py --pipeline <name> --step <step>   # run a single step of that pipeline
                                        # (use with DEBUG=True so RUN_ID is pinned and
                                        # the step finds staging left by a previous run)
"""

import os
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin") # Ensure pangolin logger is included in Prefect's logging configuration

import argparse
import importlib
import sys

from prefect.flows import Flow

from pipelines import PIPELINES
from pangolin.config.run_context import RunContext

DEFAULT_PIPELINE = "full_processing"


def _pipeline_steps(pipeline_name: str) -> dict:
    """Debug-only: auto-discover a pipeline's internal subflows (any
    module-level @flow that isn't the pipeline's own PIPELINE flow), so
    there's no separate step list to keep in sync by hand."""
    module = importlib.import_module(f"pipelines.{pipeline_name}")
    main_flow = getattr(module, "PIPELINE", None)
    return {
        name: obj
        for name, obj in vars(module).items()
        if isinstance(obj, Flow) and obj is not main_flow
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pangolin pipeline runner")
    parser.add_argument("--pipeline", default=DEFAULT_PIPELINE, help="Pipeline to run (default: %(default)s)")
    parser.add_argument("--generate", action="store_true", help="Shorthand for --pipeline generate_test_data")
    parser.add_argument("--list-pipelines", action="store_true", help="List all available pipeline names")
    parser.add_argument("--list-steps", action="store_true", help="List debuggable steps of --pipeline")
    parser.add_argument("--step", metavar="STEP", help="Run a single step of --pipeline in isolation")
    parser.add_argument("step_args", nargs="*", help="Extra positional args forwarded to --step (e.g. restore_flow's run_id)")
    return parser


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = _build_parser().parse_args(argv)  # unknown/mistyped flags raise here instead of silently running the pipeline

    if args.list_pipelines:
        for name in PIPELINES:
            print(name)
        return

    pipeline_name = "generate_test_data" if args.generate else args.pipeline

    if pipeline_name not in PIPELINES:
        available = ", ".join(PIPELINES)
        raise SystemExit(f"Unknown pipeline '{pipeline_name}'. Available: {available}")

    if args.list_steps or args.step:
        steps = _pipeline_steps(pipeline_name)
        if not steps:
            raise SystemExit(f"Pipeline '{pipeline_name}' has no debuggable steps.")

        if args.list_steps:
            for name in steps:
                print(name)
            return

        if args.step not in steps:
            raise SystemExit(f"Unknown step '{args.step}' for pipeline '{pipeline_name}'. Available: {', '.join(steps)}")
        CTX = RunContext()
        steps[args.step](CTX, *args.step_args)
        return

    PIPELINES[pipeline_name]()


if __name__ == "__main__":
    main()



