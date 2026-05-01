"""
Registers the data_pipeline as a Prefect deployment and serves it.

- Without a cron: the deployment is only triggered manually from the UI (Quick Run).
- To add a daily schedule, set the PANGOLIN_CRON env variable, e.g.:
    PANGOLIN_CRON="0 6 * * *"  ->  every day at 06:00 UTC

The flow parameters (restore_from, clear_input) are automatically
exposed in the Prefect UI under "Custom Run" → "Parameters":
  - restore_from: leave empty for normal run, or paste a backup run_id
  - clear_input:  toggle on to empty input folder after backup
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
