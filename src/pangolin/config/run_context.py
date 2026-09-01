"""
RunContext - runtime state that changes per pipeline execution.

This is intentionally separate from SETTINGS, which holds static/env config.
RunContext carries dynamic, per-run values (e.g. RUN_ID, GIT_BRANCH, GIT_SHA).
Extend this class for any future dynamic runtime variables.

Like SETTINGS, RunContext is user-extensible: if the project defines
`custom/run_context.py` with a `RunContext` subclass, `get_run_context()`
returns an instance of that subclass instead of the base one (see
`get_run_context` below and `custom/settings.py` for the same pattern).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pangolin.config.settings import get_settings


def _default_run_id() -> str:
    S = get_settings()
    # Debug mode: reuse a fixed RUN_ID so a step can be re-run standalone
    # (e.g. from the debugger) against staging data left by a previous run.
    if S.DEBUG:
        return S.DEBUG_RUN_ID
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _git(*args: str) -> str | None:
    """Run a `git` subcommand against the project's BASEPATH; None on any failure."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=get_settings().BASEPATH,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _default_git_branch() -> str:
    # In a container the working tree isn't shipped (see .dockerignore), so
    # GIT_BRANCH is baked in at build time (see docker/Dockerfile) and takes
    # priority. Locally, fall back to inspecting the actual working tree.
    return os.getenv("GIT_BRANCH") or _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"


def _default_git_sha() -> str:
    if env_sha := os.getenv("GIT_SHA"):
        return env_sha
    sha = _git("rev-parse", "--short", "HEAD")
    if not sha:
        return "unknown"
    # Flag a dirty working tree: the SHA alone would otherwise imply the
    # running code exactly matches that commit, which a local uncommitted
    # change makes untrue.
    if _git("status", "--porcelain"):
        sha += "-dirty"
    return sha


@dataclass
class RunContext:
    RUN_ID: str = field(default_factory=_default_run_id)
    GIT_BRANCH: str = field(default_factory=_default_git_branch)
    GIT_SHA: str = field(default_factory=_default_git_sha)

    def summary(self) -> str:
        return f"RUN_ID: {self.RUN_ID} | branch: {self.GIT_BRANCH} | commit: {self.GIT_SHA}"


def get_run_context() -> RunContext:
    """Return a fresh RunContext for the current run.

    If the current project defines `custom/run_context.py` with a
    `RunContext` subclass (see the scaffolded template), that subclass is
    instantiated instead — so project-specific fields declared there show up
    on `CTX` everywhere a RunContext is passed, not just in your own code.
    Falls back to the base RunContext when the project has no
    `custom/run_context.py`.
    """
    try:
        from custom.run_context import RunContext as _ProjectRunContext
    except ModuleNotFoundError as exc:
        if exc.name not in ("custom", "custom.run_context"):
            raise
        _ProjectRunContext = RunContext
    return _ProjectRunContext()
