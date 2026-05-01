"""
RunContext - runtime state that changes per pipeline execution.

This is intentionally separate from SETTINGS, which holds static/env config.
RunContext carries dynamic, per-run values (e.g. RUN_ID).
Extend this class for any future dynamic runtime variables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RunContext:
    RUN_ID: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
