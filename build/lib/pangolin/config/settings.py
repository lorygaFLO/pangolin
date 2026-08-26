from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _folder_names_from_data_structure(basepath: str) -> dict[str, str]:
    """Map SETTINGS_KEY -> folder name by reading config/data_structure.yaml."""
    structure_path = Path(basepath) / "config" / "data_structure.yaml"
    if not structure_path.exists():
        raise FileNotFoundError(
            f"data_structure.yaml not found at '{structure_path}'; "
            "folder names cannot be resolved."
        )
    with open(structure_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f) or {}
    return {
        node["_settings_key"]: key
        for key, node in schema.items()
        if isinstance(node, dict) and "_settings_key" in node
    }


class SETTINGS(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Project identity (used as UI subdomain in docker-local mode and for tagging)
    PROJECT_NAME: str = "pangolin"

    # Backend
    BACKEND_ENGINE: str = "polars"
    DUCKDB_CHUNK_SIZE: int = 100000

    # Base paths — stored as str to support both local and cloud protocols
    BASEPATH: str = "."
    DATAPATH: Optional[str] = None

    # NOTE: folder-name fields (e.g. INPUT_FOLDER_NAME, STAGING_FOLDER_NAME, ...) are
    # not declared here. They are added dynamically in `_resolve_paths` for every node
    # in data_structure.yaml that declares a `_settings_key`.

    # IO options
    DISABLE_REPORTS: bool = False
    CSV_DELIMITER: str = ";"
    OUTPUT_FORMAT: str = "parquet"

    # Debug mode: pin RUN_ID to a fixed value so staging folders from a
    # previous debug run stay reachable when re-running a single step.
    DEBUG: bool = False
    DEBUG_RUN_ID: str = "debug_run"

    # Filesystem
    FS_PROTOCOL: str = "file"
    FS_OPTIONS: dict = {}

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

        # Every _settings_key declared in data_structure.yaml becomes a SETTINGS
        # attribute here, named exactly as declared — nothing is hardcoded.
        for settings_key, folder_name in _folder_names_from_data_structure(self.BASEPATH).items():
            object.__setattr__(self, settings_key, folder_name)
        return self

    @computed_field
    @property
    def PATH_REPORTS(self) -> str:
        return self.DATAPATH + "/" + self.REPORTS_FOLDER_NAME


def get_settings() -> SETTINGS:
    """Return a fresh SETTINGS instance loaded from .env and environment."""
    return SETTINGS()