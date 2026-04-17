"""
Registers the data_pipeline as a Prefect deployment and serves it.

- Without a cron: the deployment is only triggered manually from the UI (Quick Run).
- To add a daily schedule, set the PANGOLIN_CRON env variable, e.g.:
    PANGOLIN_CRON="0 6 * * *"  →  every day at 06:00 UTC
"""

import os
import sys
from pathlib import Path

# Ensure the project root (parent of this file's directory) is on sys.path
# so that `main`, `engine`, `config`, etc. are importable regardless of
# where this script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import data_pipeline

CRON_SCHEDULE = os.getenv("PANGOLIN_CRON")  # None = no automatic schedule

if __name__ == "__main__":
    data_pipeline.serve(
        name="pangolin-daily",
        cron=CRON_SCHEDULE,  # pass None → manual-only, pass a cron string → also automatic
    )
