"""Project-specific run context.

pangolin's RunContext (RUN_ID, GIT_BRANCH, GIT_SHA) is fixed — it lives in
the library and is the same for every project. This file is where YOUR
project adds its own per-run fields, without touching the library. Anything
you declare on the RunContext class below becomes available as `CTX.<FIELD>`
everywhere a RunContext flows (pipelines, processors, your own code) —
`pangolin.config.run_context.get_run_context()` auto-detects this file and
uses this class instead of the base one.

Unlike SETTINGS (loaded from `.env`/environment), RunContext fields are
per-run *runtime* values — set them with `field(default_factory=...)` for
anything computed at run start (a trigger source, an operator name pulled
from an env var set by the scheduler, a correlation id, ...). Example:

    import os
    from dataclasses import dataclass, field
    from pangolin.config.run_context import RunContext as _BaseRunContext

    @dataclass
    class RunContext(_BaseRunContext):
        TRIGGERED_BY: str = field(default_factory=lambda: os.getenv("TRIGGERED_BY", "manual"))

    # anywhere in your code
    print(CTX.TRIGGERED_BY)

Delete this file if you don't need any project-specific run context —
pangolin falls back to the base RunContext automatically.
"""

from __future__ import annotations

from dataclasses import dataclass

from pangolin.config.run_context import RunContext as _BaseRunContext


@dataclass
class RunContext(_BaseRunContext):
    # Add your fields here, same syntax as any dataclass field — use
    # `field(default_factory=...)` for anything computed per run:
    #
    #   TRIGGERED_BY: str = field(default_factory=lambda: os.getenv("TRIGGERED_BY", "manual"))
    #   OPERATOR: str | None = None
    #
    pass
