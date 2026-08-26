"""
RunContext - runtime state that changes per pipeline execution.

This is intentionally separate from SETTINGS, which holds static/env config.
RunContext carries dynamic, per-run values (e.g. RUN_ID).
Extend this class for any future dynamic runtime variables.
"""

from __future__ import annotations

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


@dataclass
class RunContext:
    RUN_ID: str = field(default_factory=_default_run_id)
