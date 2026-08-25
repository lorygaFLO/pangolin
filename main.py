"""
Main entry point for the data processing pipeline using Prefect.

Pipelines are auto-discovered from the pipelines/ folder — each file there
defines one @flow (see pipelines/__init__.py for the discovery rules).

Usage:
    python main.py                     # run the default pipeline (full_processing)
    python main.py --pipeline <name>   # run a specific pipeline by name
    python main.py --list-pipelines    # list all available pipeline names
    python main.py --generate          # shorthand for --pipeline generate_test_data
"""

import os
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin") # Ensure pangolin logger is included in Prefect's logging configuration

import sys

from pipelines import PIPELINES

DEFAULT_PIPELINE = "full_processing"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    if "--list-pipelines" in argv:
        for name in PIPELINES:
            print(name)
        return

    if "--generate" in argv:
        pipeline_name = "generate_test_data"
    elif "--pipeline" in argv:
        pipeline_name = argv[argv.index("--pipeline") + 1]
    else:
        pipeline_name = DEFAULT_PIPELINE

    if pipeline_name not in PIPELINES:
        available = ", ".join(PIPELINES)
        raise SystemExit(f"Unknown pipeline '{pipeline_name}'. Available: {available}")

    PIPELINES[pipeline_name]()


if __name__ == "__main__":
    main()



