"""Implementation of the `pangolin prefect-server` command.

Thin wrapper around `prefect server start`: derives PREFECT_HOME from this
project's PROJECT_NAME (same as `pangolin run` / `deploy` / `bootstrap`,
see `_prefect_env.bootstrap_prefect_home`) before launching it.

Why this exists: `prefect server start` is a bare Prefect command, not a
pangolin one — pangolin can't inject env vars into a process it doesn't
launch. Run it directly and it silently falls back to Prefect's shared
global ~/.prefect, mixing this project's deployments/runs/logs with every
other local pangolin project's (the exact isolation problem this whole
PREFECT_HOME mechanism exists to avoid). This command is the one-line fix:
same isolation guarantee `pangolin run`/`deploy`/`bootstrap` already have,
without having to remember a manual `$env:PREFECT_HOME` / `export` step in
every fresh terminal.

Named `prefect-server`, not `server`, to keep it unambiguous that this
starts Prefect's own server process — not something pangolin-specific.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import typer

from pangolin.cli._prefect_env import bootstrap_prefect_home


def prefect_server(ctx: typer.Context) -> None:
    """Start a local Prefect server with this project's isolated PREFECT_HOME.

    Any extra arguments are passed through to `prefect server start` as-is,
    e.g. `pangolin prefect-server -- --host 0.0.0.0 --port 4201`.
    """
    bootstrap_prefect_home()

    prefect_exe = shutil.which("prefect")
    if prefect_exe is None:
        typer.secho(
            "Could not find the 'prefect' executable on PATH. "
            "Is prefect installed in this environment?",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    typer.secho(f"PREFECT_HOME={os.environ.get('PREFECT_HOME', '(unset)')}", fg=typer.colors.CYAN)

    cmd = [prefect_exe, "server", "start", *ctx.args]
    try:
        completed = subprocess.run(cmd, env=os.environ)
    except KeyboardInterrupt:
        # Ctrl+C: the child (sharing our console) already got SIGINT/CTRL_C
        # and is shutting down on its own — just exit quietly like the bare
        # `prefect server start` would.
        raise typer.Exit(code=130)

    raise typer.Exit(code=completed.returncode)
