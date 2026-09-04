"""Derive a per-project PREFECT_HOME in local (non-Docker) mode.

Prefect falls back to a single, machine-wide state directory (`~/.prefect`,
one shared SQLite DB) whenever `PREFECT_HOME` isn't set. Every pangolin
project run locally on the same machine/user then lands in that same
database — deployments, runs and logs from unrelated projects all show up
mixed together in the same Prefect UI.

Docker mode already avoids this: each project gets its own containers/
volumes, namespaced by `PROJECT_NAME` (see docker-compose.yml). This module
gives local mode the same guarantee — each project gets its own
`<project>/.prefect/<PROJECT_NAME>` state directory, so different pangolin
projects on the same machine never share a Prefect server/database.

Must run before `prefect` is imported anywhere in the process: Prefect
resolves PREFECT_HOME as part of its settings machinery, so this has to
execute at the very top of every CLI entry point that might touch Prefect
(see call sites in `_discovery.load_pipelines` and `bootstrap_cmd.py`).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values


def bootstrap_prefect_home() -> None:
    """Set ``os.environ['PREFECT_HOME']`` for a local-mode run.

    No-op when:
    - `PREFECT_HOME` is already set (an explicit shell export or a Docker
      container's own env always wins over anything derived here);
    - `PANGOLIN_MODE` is not "local" (docker-local/cloud isolate via
      containers instead, see docker-compose.yml's `PROJECT_NAME`).

    The value is read from the project's `.env` (`PREFECT_HOME`, or a
    default derived from `PROJECT_NAME`) so it stays in sync with whatever
    the user set there — see PREFECT_HOME in template.env.
    """
    if os.getenv("PREFECT_HOME"):
        return

    if os.getenv("PANGOLIN_MODE", "local").lower() != "local":
        return

    env_path = Path.cwd() / ".env"
    values = dotenv_values(env_path) if env_path.is_file() else {}

    project_name = values.get("PROJECT_NAME") or "pangolin"
    prefect_home = values.get("PREFECT_HOME") or f".prefect/{project_name}"

    os.environ["PREFECT_HOME"] = str((Path.cwd() / prefect_home).resolve())
