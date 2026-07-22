"""
Processor Logger
=================
Minimal structured logger for pipeline processors.

Wraps the standard :mod:`logging` module and automatically prefixes every
message with the **processor name** and (optionally) the **file** currently
being processed.

Usage inside a processor (``self.log`` is wired in ``BaseProcessor``)::

    self.log.info("Starting validation")
    self.log.debug("Column list: %s", cols)

    with self.log.processing("invoices_2024.csv"):
        self.log.info("Loaded 150 rows")
        self.log.warning("3 rows have null keys")
        self.log.debug("Null keys in rows: %s", bad_rows)

Output::

    [INFO] [MyProcessor] Starting validation
    [INFO] [MyProcessor | invoices_2024.csv] Loaded 150 rows
    [WARNING] [MyProcessor | invoices_2024.csv] 3 rows have null keys

To enable DEBUG output, set the environment variable::

    PANGOLIN_LOG_LEVEL=DEBUG
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Optional, Generator

# ------------------------------------------------------------------
# One-time setup: ensure pangolin.* logs are visible and Prefect-aware
# ------------------------------------------------------------------

_NAMESPACE = "pangolin"
_root_logger = logging.getLogger(_NAMESPACE)

# Allow the user to control verbosity via env var (default: INFO)
_level_name = os.environ.get("PANGOLIN_LOG_LEVEL", "INFO").upper()
_level = getattr(logging, _level_name, logging.INFO)

# Add a console handler only if none exists yet (avoids duplicates on reimport)
if not _root_logger.handlers:
    _root_logger.setLevel(_level)
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    _root_logger.addHandler(_handler)
else:
    _root_logger.setLevel(_level)


class ProcessorLogger:
    """
    Thin wrapper around :mod:`logging` that auto-prefixes
    processor name and (optionally) the current file being processed.

    All standard levels are available:

    * ``debug()``     — verbose detail, useful during development
    * ``info()``      — normal operational messages
    * ``warning()``   — something unexpected but non-fatal
    * ``error()``     — something failed
    * ``exception()`` — like error, but includes the traceback

    Parameters:
        name:   Identifier for the processor / component.
        logger: Optional existing :class:`logging.Logger`; when *None*
                a new one is created under the ``pangolin.<name>`` namespace.
    """

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self._name = name
        self._logger = logger or logging.getLogger(f"{_NAMESPACE}.{name}")
        self._current_file: Optional[str] = None

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------

    @contextmanager
    def processing(self, file_name: str) -> Generator[None, None, None]:
        """
        Set the *current file* context for the duration of the block.

        Can be nested safely — the previous context is restored on exit.
        """
        prev = self._current_file
        self._current_file = file_name
        try:
            yield
        finally:
            self._current_file = prev

    def set_file(self, file_name: Optional[str]) -> None:
        """Manually set (or clear) the current file context."""
        self._current_file = file_name

    # ------------------------------------------------------------------
    # Prefix builder
    # ------------------------------------------------------------------

    @property
    def _prefix(self) -> str:
        if self._current_file:
            return f"[{self._name} | {self._current_file}]"
        return f"[{self._name}]"

    # ------------------------------------------------------------------
    # Logging methods (mirror stdlib interface)
    # ------------------------------------------------------------------

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Verbose detail — visible only when PANGOLIN_LOG_LEVEL=DEBUG."""
        self._logger.debug(f"{self._prefix} {msg}", *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Normal operational messages."""
        self._logger.info(f"{self._prefix} {msg}", *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Something unexpected but non-fatal."""
        self._logger.warning(f"{self._prefix} {msg}", *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Something failed."""
        self._logger.error(f"{self._prefix} {msg}", *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Like ``error()`` but also logs the current exception traceback."""
        self._logger.exception(f"{self._prefix} {msg}", *args, **kwargs)
