# Pangolin — Data Ingestion, Validation & Transformation Pipeline

Pangolin is a flexible, modular data processing pipeline built on top of **Prefect** and **Polars**. It automates multi-stage ingestion, validation, transformation, and delivery of data files, ensuring data quality and compliance with user-defined rules at every step.

This project is especially valuable for organizations that need to routinely process and especially validate data from third-party sources. It provides a declarative, YAML-driven approach to defining pipeline stages, making it easy to configure new rules and extend the system without touching core code.

## Key Features

* **Prefect-orchestrated pipeline**: Each stage runs as a Prefect subflow with full observability and retry support
* **Declarative YAML registries**: Define validation rules, transformations, and routing logic in plain YAML — no Python required for most customizations
* **Polars backend**: Fast, memory-efficient dataframe processing
* **fsspec integration**: Filesystem-agnostic I/O; swap local storage for S3, GCS, or Azure with a one-line config change
* **DataFacility**: A YAML-driven data access layer that maps the project's folder structure into a navigable Python object tree
* **Detailed per-stage reports**: HTML reports generated automatically for every stage and processed file
* **Non-destructive processing**: Input files are never modified; every stage writes to its own staging folder
* **Extensible with decorators**: Add new validators/transformers with a single `@register_validator` / `@register_transformer` decorator — no manual dict wiring

## Project Architecture

### Directory Structure

```
/
├── main.py                     # Pipeline entry point (Prefect flows)
├── deploy.py                   # ← lives in docker/ — see below
├── example.env                 # Environment variable template
├── pyproject.toml              # Project metadata & dependencies
├── docker/
│   └── deploy.py               # Prefect deployment: registers flow + serves it (manual & scheduled runs)
├── config/
│   ├── settings.py             # Settings loader (reads .env, builds paths)
│   ├── constants.py            # System-wide constants
│   ├── data_structure.yaml     # Declarative folder/file schema (DataFacility)
│   └── registries/
│       ├── 0_raw_validation.yaml    # Stage 0 — raw input validation rules
│       ├── 1_dispatcher.yaml        # Stage 1 — file routing rules
│       ├── 2_transform_registry.yaml # Stage 2 — transformation rules
│       ├── 3_validation.yaml        # Stage 3 — post-transform validation
│       ├── 4_cross_validation.yaml  # Stage 4 — cross-file validation
│       └── 5_dispatcher.yaml        # Stage 5 — final delivery routing
├── engine/
│   ├── DataFacility.py         # YAML-driven data access layer
│   ├── reporter.py             # Report generation
│   ├── core/
│   │   ├── exceptions.py       # Custom pipeline exceptions
│   │   └── logger.py           # Per-processor logger
│   └── processors/
│       ├── BaseProcessor.py    # Shared processor base class
│       ├── DataValidator.py    # Validation processor
│       ├── DataTranformer.py   # Transformation processor
│       └── FileDispatcher.py  # File routing processor
├── utils/
│   ├── validators.py           # Built-in validator functions
│   ├── transformers.py         # Built-in transformer functions
│   └── fs_wrapper.py           # fsspec filesystem wrapper
└── data/
    ├── input/                  # Drop input files here
    ├── staging/                # Per-run intermediate data (auto-created)
    ├── delivery/               # Final outputs (timestamped per run)
    └── reports/                # Pipeline reports (timestamped per run)
```

### Pipeline Stages

The pipeline runs 6 sequential Prefect subflows in the example:

| # | Subflow | Processor | Description |
|---|---------|-----------|-------------|
| 0 | Raw Data Validation | `Validator` | Validates raw input files against `0_raw_validation.yaml` |
| 1 | Raw Data Dispatch | `FileDispatcher` | Routes validated files into typed sub-folders (e.g. `SALES`, `INVENTORY`) |
| 2 | Data Transformation | `DataTransformer` | Applies enrichment, column transforms, and derived columns |
| 3 | Transformed Data Validation | `Validator` | Re-validates post-transform data |
| 4 | Cross Validation | `Validator` | Cross-file consistency checks |
| 5 | Final Data Dispatch | `FileDispatcher` | Routes processed files to the delivery folder by region/type |

Each stage reads from the previous stage's output folder (under `data/staging/<RUN_ID>/`) and writes to the next. Staging folders are timestamped per run to keep runs fully isolated and traceable.

### DataFacility

`DataFacility` maps `config/data_structure.yaml` onto the filesystem as a navigable Python object tree. Any processor can access paths, read files, and check existence without hardcoding paths:

```python
from engine.DataFacility import get_project_data

D = get_project_data()
D.input                            # data/input/
D.staging                          # data/staging/<RUN_ID>/
D.static.mappings.product_mapping  # data/static/mappings/product_mapping.csv

node = D.static.mappings.product_mapping
node.exists()    # True / False
node.read()      # polars.DataFrame
node.path        # pathlib.Path
```

## Setup

### Prerequisites

* Python ≥ 3.10
* A running [Prefect](https://docs.prefect.io/) server (optional for local runs — Prefect can also run without a server in local mode)

### Installation

```bash
pip install -e .
```

### Configuration

1. Copy `example.env` to `.env` at the project root and fill in the values:

```env
BACKEND_ENGINE=polars          # Only "polars" is supported in this release
FS_PROTOCOL=file               # fsspec protocol: "file", "s3", "gcs", "abfs", …
# FS_OPTIONS={"key": "...", "secret": "..."}  # JSON string of fsspec options (optional)

BASEPATH=C:\path\to\repo
DATAPATH=C:\path\to\data       # Absolute, or relative to BASEPATH

INPUT_FOLDER_NAME=input
STAGING_FOLDER_NAME=staging
DELIVERY_FOLDER_NAME=delivery
REPORTS_FOLDER_NAME=reports
BACKUP_FOLDER_NAME=backup

CSV_DELIMITER=;
OUTPUT_FORMAT=parquet          # "parquet" or "csv"
DISABLE_REPORTS=False
```

2. Place input files in the `data/input/` folder (or the path configured in `.env`).

### Running the Pipeline

#### Option A — Direct execution (no UI, no server)

```bash
python main.py
```

Runs the full 6-stage pipeline immediately. Prefect operates in local/ephemeral mode — no server required, but no UI either.

#### Option B — With Prefect UI (manual trigger + observability)

Open two terminals:

```bash
# Terminal 1 — start the Prefect server and UI
prefect server start
```

```bash
# Terminal 2 — register the deployment and keep it listening
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
python docker/deploy.py
```

Then open `http://127.0.0.1:4200` → **Deployments** → `pangolin-daily` → **Quick Run**.

To also enable a daily automatic schedule, set the env variable before running:

```bash
set PANGOLIN_CRON=0 6 * * *
python docker/deploy.py
```

Each run is identified by a unique `RUN_ID` timestamp (`YYYYMMDD_HHMMSS`) stamped on every staging, delivery, and report folder.

## Configuration Guide

### Registry Files

Each stage is driven by a YAML registry file. Files are matched against entries using glob patterns.

#### Validation Registry (e.g. `0_raw_validation.yaml`)

```yaml
"*sales*":
  validators:
    is_empty_dataframe:           # no params needed
    required_columns:
      - product_id
      - price
      - quantity
    validate_product_ids:
      product_id_column: product_id
      product_id_master_column: product_id
```

#### Transformation Registry (`2_transform_registry.yaml`)

```yaml
"*_sales_*":
  transforms:
    - name: "enrich_with_mapping"
      function: "enrich_with_mapping"
      params:
        mapping_file: "D.static.mappings.product_mapping"
        df_join_column: ["product_id"]
        mapping_key_column: ["product_id"]
        columns_to_add: ["product_name", "brand"]
      order: 1
    - name: "case_transform"
      function: "case_transform"
      params:
        columns: ["product_name", "brand"]
        to_uppercase: true
      order: 2
```

#### Dispatcher Registry (e.g. `1_dispatcher.yaml`)

```yaml
"*sales*":    "SALES"
"*inventory*": "INVENTORY"
```

Files matching a pattern are routed to the named sub-folder inside the output directory.

### Data Structure (`config/data_structure.yaml`)

Defines the project's folder/file schema consumed by `DataFacility`. Use `_settings_key` to link a folder name to a `.env` variable, and `_timestamped: true` to automatically append the `RUN_ID`:

```yaml
staging:
  _settings_key: "STAGING_FOLDER_NAME"
  _timestamped: true
  0_validator:
    _pattern_matching: true
```

## Extending the Pipeline

### Adding a Custom Validator

Validators live in `utils/validators.py`. Decorate with `@register_validator` — no manual dict wiring required:

```python
from utils.validators import register_validator
import polars as pl

@register_validator
def no_negative_values(df: pl.DataFrame, messages: list, params=None) -> bool:
    """Fail if any numeric column contains negative values."""
    cols = params.get("columns", df.columns) if params else df.columns
    for col in cols:
        if df[col].dtype in (pl.Int64, pl.Float64) and (df[col] < 0).any():
            messages.append(f"Column '{col}' contains negative values.")
            return False
    return True
```

Then reference it by name in any registry YAML:

```yaml
"*sales*":
  validators:
    no_negative_values:
      columns: ["price", "quantity"]
```

**Signature contract:**
- `df` — `polars.DataFrame`
- `messages` — mutable list; append human-readable issue descriptions
- `params` — optional extra config (dict, list, scalar, or `None`)
- Return `True` for pass, `False` for fail; raise `ValueError` to abort the entire pipeline

### Adding a Custom Transformer

Transformers live in `utils/transformers.py`. Decorate with `@register_transformer`:

```python
from utils.transformers import register_transformer
import polars as pl

@register_transformer
def fill_nulls(df: pl.DataFrame, columns: list, fill_value=0, messages: list = None) -> pl.DataFrame:
    """Replace null values in specified columns."""
    df = df.with_columns([pl.col(c).fill_null(fill_value) for c in columns])
    if messages is not None:
        messages.append(f"Filled nulls in {columns} with {fill_value}")
    return df
```

Reference it in `2_transform_registry.yaml`:

```yaml
"*_sales_*":
  transforms:
    - name: "fill_nulls"
      function: "fill_nulls"
      params:
        columns: ["quantity", "price"]
        fill_value: 0
      order: 5
```

**Signature contract:**
- `df` — `polars.DataFrame` (first positional argument)
- `messages` — optional mutable list for operation notes
- Additional keyword arguments map directly to `params` keys in the YAML
- Must return a `polars.DataFrame` — never `None`

## Contributing

Contributions are welcome! Priority areas:

* **Dockerization** *(in progress)*: `docker/deploy.py` and the Prefect deployment are ready. Still needed: `Dockerfile`, `docker-compose.yml` (PostgreSQL + prefect-server + pangolin services), `.dockerignore`, and `requirements-docker.txt` (strips Windows-only deps). Cloud-native I/O (S3/GCS/Azure via `FS_PROTOCOL`/`FS_OPTIONS`) and runtime-injected credentials are planned.
* **Full Prefect Integration**: Move beyond basic `@flow` decorators — add deployment manifests (`prefect.yaml`), work pools, artifacts, Prefect secrets/variables blocks, scheduled/triggered runs, and failure notifications.
* **New File Format Support**: Add support for Excel, JSON, or other formats
* **Additional Validators/Transformers**: Implement new reusable functions
* **Cloud Storage**: Expand and document S3/GCS/Azure usage via `FS_PROTOCOL` and `FS_OPTIONS`
* **Documentation & Examples**: Improve guides and add realistic end-to-end examples

