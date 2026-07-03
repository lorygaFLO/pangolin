"""
Batch — in-memory contract between pipeline steps within a medallion layer.

A Batch replaces the on-disk staging folder as the hand-off between steps:
each processor exposes a pure `run(batch) -> batch` method that operates on
DataFrames in memory. Persistence happens only at the layer boundaries
(load_batch at the start, save_batch at the end), owned by the orchestration
layer — never by the processors themselves.

Files that fail a step are moved to `failed` (with their error messages,
already reported by the step's Reporter) and disappear from the flow,
mirroring the previous "not saved to next staging folder" semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import polars as pl


@dataclass
class BatchItem:
    """A single in-flight file: its data plus routing/lineage metadata."""
    df: pl.DataFrame
    relative_path: str                      # registry pattern-matching key (may be rewritten by dispatchers)
    source_path: Optional[str] = None       # original on-disk path (informational)
    pattern: Optional[str] = None           # last matched registry pattern
    lineage: List[str] = field(default_factory=list)  # step names successfully applied


@dataclass
class Batch:
    """Collection of in-flight files, keyed by relative_path."""
    items: Dict[str, BatchItem] = field(default_factory=dict)
    failed: Dict[str, List[str]] = field(default_factory=dict)  # relative_path -> error messages

    def add(self, item: BatchItem) -> None:
        self.items[item.relative_path] = item

    def fail(self, relative_path: str, messages: List[str]) -> None:
        """Remove a file from the flow and record why it failed."""
        self.items.pop(relative_path, None)
        self.failed.setdefault(relative_path, []).extend(messages)

    def rename(self, old_relative_path: str, new_relative_path: str) -> BatchItem:
        """Rewrite an item's relative_path (used by dispatchers for in-memory routing)."""
        item = self.items.pop(old_relative_path)
        item.relative_path = new_relative_path
        self.items[new_relative_path] = item
        return item

    @property
    def is_empty(self) -> bool:
        return not self.items

    def __len__(self) -> int:
        return len(self.items)
