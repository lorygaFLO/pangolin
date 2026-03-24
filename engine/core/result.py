"""
Processor Result Model
=======================
Structured outcome representation for pipeline processors.

* ``FileResult``      — per-file outcome (pass/fail, record count, messages)
* ``ProcessorOutcome`` — enum: SUCCESS | PARTIAL_SUCCESS | FAILED | NO_INPUT
* ``ProcessorResult``  — aggregate outcome with policy enforcement

The calling flow uses ``ProcessorResult.raise_on_failure()`` to decide
how strictly to treat partial successes.
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.core.exceptions import (
    AllFilesFailedError,
    NoInputFilesError,
    PartialSuccessError,
)


class ProcessorOutcome(Enum):
    """Outcome classification for a processor's batch run."""
    SUCCESS = "SUCCESS"                    # All files passed
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"    # Some passed, some failed
    FAILED = "FAILED"                      # All files failed
    NO_INPUT = "NO_INPUT"                  # No files found


@dataclass
class FileResult:
    """Outcome for a single file processed within a batch."""
    file_path: str
    relative_path: str
    success: bool
    record_count: Optional[int] = None
    messages: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "PASSED" if self.success else "FAILED"
        rows = f" ({self.record_count} rows)" if self.record_count else ""
        return f"<FileResult [{status}] {self.relative_path}{rows}>"


@dataclass
class ProcessorResult:
    """
    Aggregate result for a processor's ``execute()`` call.

    Attributes:
        processor_name: Identifier of the processor step.
        file_results:   Per-file outcomes collected during execution.

    Derived properties compute totals and the overall outcome automatically.
    """
    processor_name: str
    file_results: List[FileResult] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def total_files(self) -> int:
        return len(self.file_results)

    @property
    def passed_files(self) -> int:
        return sum(1 for f in self.file_results if f.success)

    @property
    def failed_files(self) -> int:
        return sum(1 for f in self.file_results if not f.success)

    @property
    def total_records(self) -> int:
        return sum(f.record_count or 0 for f in self.file_results)

    @property
    def outcome(self) -> ProcessorOutcome:
        if self.total_files == 0:
            return ProcessorOutcome.NO_INPUT
        if self.passed_files == self.total_files:
            return ProcessorOutcome.SUCCESS
        if self.passed_files == 0:
            return ProcessorOutcome.FAILED
        return ProcessorOutcome.PARTIAL_SUCCESS

    @property
    def summary(self) -> str:
        """One-line human-readable summary for log output."""
        return (
            f"Outcome={self.outcome.value} | "
            f"Files: {self.passed_files}/{self.total_files} passed, "
            f"{self.failed_files} failed | "
            f"Total records: {self.total_records}"
        )

    # ------------------------------------------------------------------
    # Policy enforcement
    # ------------------------------------------------------------------

    def raise_on_failure(self, *, allow_partial: bool = True) -> None:
        """
        Raise an appropriate exception based on outcome and policy.

        Args:
            allow_partial: If ``True``, partial success is **not** an error
                           (a WARNING is logged but the flow continues).
                           If ``False``, partial success raises
                           ``PartialSuccessError``.

        Raises:
            NoInputFilesError:    when ``outcome`` is ``NO_INPUT``
            AllFilesFailedError:  when ``outcome`` is ``FAILED``
            PartialSuccessError:  when ``outcome`` is ``PARTIAL_SUCCESS``
                                  and ``allow_partial`` is ``False``
        """
        if self.outcome == ProcessorOutcome.NO_INPUT:
            raise NoInputFilesError(self.processor_name, "<batch>")

        if self.outcome == ProcessorOutcome.FAILED:
            raise AllFilesFailedError(
                f"[{self.processor_name}] All {self.total_files} file(s) failed processing.",
                result=self,
            )

        if self.outcome == ProcessorOutcome.PARTIAL_SUCCESS and not allow_partial:
            raise PartialSuccessError(
                f"[{self.processor_name}] Partial success: "
                f"{self.passed_files}/{self.total_files} passed.",
                result=self,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def add(self, file_result: FileResult) -> None:
        """Append a file result."""
        self.file_results.append(file_result)

    @property
    def failed_file_paths(self) -> List[str]:
        return [f.relative_path for f in self.file_results if not f.success]

    @property
    def passed_file_paths(self) -> List[str]:
        return [f.relative_path for f in self.file_results if f.success]

    def __repr__(self) -> str:
        return f"<ProcessorResult [{self.processor_name}] {self.summary}>"
