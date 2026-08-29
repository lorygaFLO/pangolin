from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, computed_field, field_validator, model_validator
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
    PROJECT_NAME: str = Field(
        "pangolin",
        description="Project identity. Used as the Prefect UI subdomain in docker-local mode and for run tagging.",
    )

    # Backend
    BACKEND_ENGINE: str = Field(
        "polars", description="Dataframe engine. Only 'polars' is supported in this release."
    )
    DUCKDB_CHUNK_SIZE: int = Field(
        100000, description="Reserved for a future DuckDB backend; unused today."
    )

    # Base paths — stored as str to support both local and cloud protocols
    BASEPATH: str = Field(
        ".",
        description="Project root. Resolved to an absolute path at startup; also the base DATAPATH is resolved against when DATAPATH is relative.",
    )
    DATAPATH: Optional[str] = Field(
        None,
        description="Where data/ lives. Defaults to '<BASEPATH>/data' when FS_PROTOCOL='file'. REQUIRED (container/bucket name or prefix) for cloud protocols.",
    )

    # NOTE: folder-name fields (e.g. INPUT_FOLDER_NAME, STAGING_FOLDER_NAME, ...) are
    # not declared here. They are added dynamically in `_resolve_paths` for every node
    # in data_structure.yaml that declares a `_settings_key` — one project's set of
    # folder settings can differ from another's, so there is nothing fixed to declare.

    # IO options
    DISABLE_REPORTS: bool = Field(False, description="Skip HTML validation report generation.")
    CSV_DELIMITER: str = Field(";", description="Delimiter used when reading/writing CSV files.")
    OUTPUT_FORMAT: str = Field("parquet", description="Staging/output file format: 'csv' or 'parquet'.")

    # Debug mode: pin RUN_ID to a fixed value so staging folders from a
    # previous debug run stay reachable when re-running a single step.
    DEBUG: bool = Field(
        False,
        description="When True, pins RUN_ID to DEBUG_RUN_ID so `pangolin step` can find staging left by a previous run.",
    )
    DEBUG_RUN_ID: str = Field("debug_run", description="RUN_ID used when DEBUG=True.")

    # Filesystem
    FS_PROTOCOL: str = Field(
        "file", description="fsspec protocol: 'file' for local disk, or 'az' / 's3' / 'gcs' for cloud storage."
    )
    FS_OPTIONS: dict = Field(
        default_factory=dict,
        description="Extra fsspec storage options (credentials, endpoint, etc.) for a non-local FS_PROTOCOL, as a JSON object.",
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
    """Return a fresh SETTINGS instance loaded from .env and environment.

    If the current project defines `custom/settings.py` with a `SETTINGS`
    class subclassing this one (see the scaffolded template), that subclass
    is instantiated instead — so project-specific fields declared there
    (e.g. `TRAINING_EPOCHS: int = 10`) show up as `S.TRAINING_EPOCHS`
    everywhere `get_settings()` is called, not just in your own code.
    Falls back to the base SETTINGS when the project has no custom/settings.py.
    """
    try:
        from custom.settings import SETTINGS as _ProjectSettings
    except ModuleNotFoundError as exc:
        if exc.name not in ("custom", "custom.settings"):
            raise
        _ProjectSettings = SETTINGS
    return _ProjectSettings()