"""
Pipeline Exception Taxonomy
============================
Structured exception hierarchy for pipeline processors.
Separates "expected business failures" from "unexpected runtime errors"
so that flows can apply clear policies (fail / warn / retry).

Hierarchy:
    PipelineError                     ← base for all pipeline-specific errors
    ├── NoInputFilesError             ← no files found in input folder
    └── AllFilesFailedError           ← every file failed validation/transform
"""


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
    """

    def __init__(self, message: str):
        super().__init__(message)

