from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SETTINGS(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Backend
    BACKEND_ENGINE: str = "polars"
    DUCKDB_CHUNK_SIZE: int = 100000

    # Base paths — stored as str to support both local and cloud protocols
    BASEPATH: str = "."
    DATAPATH: Optional[str] = None

    # Folder names
    INPUT_FOLDER_NAME: str = "input"
    STAGING_FOLDER_NAME: str = "staging"
    DELIVERY_FOLDER_NAME: str = "delivery"
    REPORTS_FOLDER_NAME: str = "reports"
    BACKUP_FOLDER_NAME: str = "backup"

    # IO options
    DISABLE_REPORTS: bool = False
    CSV_DELIMITER: str = ";"
    OUTPUT_FORMAT: str = "parquet"

    # Filesystem
    FS_PROTOCOL: str = "file"
    FS_OPTIONS: dict = {}

    # Run ID (generated per instance, not from env)
    RUN_ID: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )

    @field_validator("BACKEND_ENGINE")
    @classmethod
    def _validate_backend(cls, v: str) -> str:
        if v not in ("polars",):
            raise ValueError(
                f"Invalid BACKEND_ENGINE: {v}. Only polars supported in this release."
            )
        return v

    @field_validator("OUTPUT_FORMAT")
    @classmethod
    def _validate_output_format(cls, v: str) -> str:
        v = v.lower()
        if v not in {"csv", "parquet"}:
            raise ValueError(f"Unsupported OUTPUT_FORMAT: {v}")
        return v

    @field_validator("BASEPATH", mode="before")
    @classmethod
    def _coerce_empty_basepath(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return "."
        if isinstance(v, Path):
            return str(v)
        return v

    @field_validator("DATAPATH", mode="before")
    @classmethod
    def _coerce_empty_datapath(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        if isinstance(v, Path):
            return str(v)
        return v

    @model_validator(mode="after")
    def _resolve_paths(self) -> SETTINGS:
        if self.FS_PROTOCOL == "file":
            # Local filesystem: resolve to absolute paths
            bp = Path(self.BASEPATH)
            if not bp.is_absolute():
                bp = Path.cwd() / bp
            self.BASEPATH = str(bp.resolve())

            if self.DATAPATH is None:
                self.DATAPATH = str(Path(self.BASEPATH) / "data")
            else:
                dp = Path(self.DATAPATH)
                if not dp.is_absolute():
                    self.DATAPATH = str(Path(self.BASEPATH) / dp)
        else:
            # Cloud protocols (az, s3, gcs, etc.): DATAPATH is a container/prefix
            if self.DATAPATH is None:
                raise ValueError(
                    f"DATAPATH is required when FS_PROTOCOL='{self.FS_PROTOCOL}'. "
                    "Set it to your container name or bucket prefix."
                )
            # BASEPATH is not meaningful for cloud; keep as-is for config loading
            bp = Path(self.BASEPATH)
            if not bp.is_absolute():
                bp = Path.cwd() / bp
            self.BASEPATH = str(bp.resolve())
        return self

    # Derived paths
    @computed_field
    @property
    def PATH_REPORTS(self) -> str:
        return self.DATAPATH + "/" + self.REPORTS_FOLDER_NAME

    @staticmethod
    def create_directories(*paths: str) -> None:
        """Create local folders if they do not exist. For cloud, use FSWrapper.makedirs."""
        for p in paths:
            os.makedirs(p, exist_ok=True)


def get_settings() -> SETTINGS:
    """Return a fresh SETTINGS instance loaded from .env and environment."""
    return SETTINGS()