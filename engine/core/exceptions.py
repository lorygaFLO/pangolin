"""
Pipeline Exception Taxonomy
============================
Structured exception hierarchy for pipeline processors.
Separates "expected business failures" from "unexpected runtime errors"
so that flows can apply clear policies (fail / warn / retry).

Hierarchy:
    PipelineError                     ← base for all pipeline-specific errors
    ├── NoInputFilesError             ← no files found in input folder
    ├── AllFilesFailedError           ← every file failed validation/transform
    ├── PartialSuccessError           ← some files passed, some failed
    └── ProcessorRuntimeError         ← unexpected error during processing
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.core.result import ProcessorResult


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class PipelineError(Exception):
    """Base exception for all pipeline-domain errors."""
    pass


# ---------------------------------------------------------------------------
# Input Errors
# ---------------------------------------------------------------------------

class NoInputFilesError(PipelineError):
    """
    Raised when a processor finds zero files to process.

    This typically signals a pipeline configuration error or a missing
    upstream step.  Flows should treat this as a **hard failure**.
    """

    def __init__(self, processor_name: str, input_path: str):
        self.processor_name = processor_name
        self.input_path = input_path
        super().__init__(
            f"[{processor_name}] No input files found in '{input_path}'. "
            f"Check previous pipeline steps or input configuration."
        )


# ---------------------------------------------------------------------------
# Processing-Outcome Errors
# ---------------------------------------------------------------------------

class AllFilesFailedError(PipelineError):
    """
    Raised when every file in the batch fails validation or transformation.

    Carries the full ``ProcessorResult`` so the caller can inspect per-file
    details if needed.
    """

    def __init__(self, message: str, result: ProcessorResult | None = None):
        super().__init__(message)
        self.result = result


class PartialSuccessError(PipelineError):
    """
    Raised (optionally) when some — but not all — files pass processing.

    Whether this is raised depends on the flow's policy:
      * ``allow_partial=True``  → **not** raised, flow continues with a WARNING
      * ``allow_partial=False`` → raised, flow fails

    Carries the full ``ProcessorResult``.
    """

    def __init__(self, message: str, result: ProcessorResult | None = None):
        super().__init__(message)
        self.result = result


# ---------------------------------------------------------------------------
# Runtime Errors
# ---------------------------------------------------------------------------

class ProcessorRuntimeError(PipelineError):
    """
    Wraps unexpected / unhandled exceptions that occur during processing.

    Use this when the root cause is *not* a business-level failure
    (e.g. I/O error, bug in a transformer function, OOM, etc.).
    """

    def __init__(self, processor_name: str, original: Exception):
        self.processor_name = processor_name
        self.original = original
        super().__init__(
            f"[{processor_name}] Unexpected runtime error: {original!r}"
        )
