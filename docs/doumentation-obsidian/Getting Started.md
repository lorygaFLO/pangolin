# Getting Started

This guide walks you through setting up Pangolin from scratch and running the pipeline for the first time.

---

## Prerequisites

- **Python 3.10+**
- **pip** (or your preferred package manager)

---

## 1. Clone the Repository

```bash
git clone <repo-url> pangolin
cd pangolin
```

---

## 2. Create a Virtual Environment

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -e .
```

This installs Pangolin in editable mode along with all dependencies declared in `pyproject.toml` (Prefect, Polars, Pandas, PyYAML, fsspec, etc.).

---

## 4. Configure the Environment

Copy the example environment file and edit it:

```bash
cp example.env .env
```

Open `.env` and set the required values:

```ini
# Backend engine (only "polars" is supported)
BACKEND_ENGINE=polars

# Filesystem protocol ("file" for local, "s3", "gcs", "abfs" for cloud)
FS_PROTOCOL=file

# Base path to the repository root
BASEPATH=C:\path\to\pangolin

# Path to the data folder (absolute or relative to BASEPATH)
DATAPATH=C:\path\to\pangolin\data

# Folder names (these match the top-level keys in data_structure.yaml)
INPUT_FOLDER_NAME=input
STAGING_FOLDER_NAME=staging
DELIVERY_FOLDER_NAME=delivery
REPORTS_FOLDER_NAME=reports
BACKUP_FOLDER_NAME=backup

# Set to True to skip report generation
DISABLE_REPORTS=False

# CSV settings
CSV_DELIMITER=;

# Output format for processed files: "csv" or "parquet"
OUTPUT_FORMAT=parquet
```

> [!tip]
> On Linux/macOS, use forward slashes for paths. On Windows, both `\` and `/` work.

### Cloud Storage (Optional)

To use S3, GCS, or Azure Blob instead of local disk:

```ini
FS_PROTOCOL=s3
FS_OPTIONS={"key": "AKIAIOSFODNN7EXAMPLE", "secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}
```

`FS_OPTIONS` accepts a JSON string with any `fsspec` storage options for the chosen protocol.

---

## 4b. Adapting `settings.py` to Your Own Project

The `SETTINGS` class in `config/settings.py` is a **singleton** that reads all its values from the `.env` file. You do **not** need to modify `settings.py` for normal usage — just change `.env`. However, if you are building your own project on top of Pangolin, here is what you can customize:

### Adding a New Setting

1. Add the variable to your `.env`:
   ```ini
   MY_CUSTOM_OPTION=some_value
   ```

2. Read it inside `SETTINGS.__init__()` using the helper functions:
   ```python
   # In config/settings.py, inside __init__:
   self.MY_CUSTOM_OPTION = _as_str(os.getenv("MY_CUSTOM_OPTION"), "default_value")
   ```

3. Access it anywhere in your code:
   ```python
   from config.settings import get_settings
   S = get_settings()
   print(S.MY_CUSTOM_OPTION)
   ```

### Helper Functions

`settings.py` provides three type-safe helpers for reading environment variables:

| Helper | Returns | Example |
|--------|---------|---------|
| `_as_str(val, default)` | `str` or `None` | `_as_str(os.getenv("MY_VAR"), "fallback")` |
| `_as_bool(val, default)` | `bool` | `_as_bool(os.getenv("ENABLE_X"), False)` — accepts `1`, `true`, `yes`, `y` |
| `_as_int(val, default)` | `int` | `_as_int(os.getenv("BATCH_SIZE"), 1000)` |

### Changing Folder Names

The `INPUT_FOLDER_NAME`, `STAGING_FOLDER_NAME`, etc. are logical folder names that match the `_settings_key` values in `data_structure.yaml`. If you rename them in `.env`, also update `data_structure.yaml` to match (see [[Data Structure & DataFacility]]).

### Key Properties You Get for Free

| Property | Value | Description |
|----------|-------|-------------|
| `S.RUN_ID` | `"20260324_185705"` | Unique timestamp for the current run, generated automatically |
| `S.BASEPATH` | `Path(...)` | Absolute path to the project root |
| `S.DATAPATH` | `Path(...)` | Absolute path to the data folder |
| `S.BACKEND_ENGINE` | `"polars"` | The DataFrame backend (only `polars` supported) |
| `S.CSV_DELIMITER` | `";"` | Delimiter used for reading/writing CSV files |
| `S.OUTPUT_FORMAT` | `"parquet"` | Output file format (`csv` or `parquet`) |
| `S.FS_PROTOCOL` | `"file"` | Filesystem protocol for `fsspec` |
| `S.FS_OPTIONS` | `{}` | Storage options for cloud protocols |
| `S.DISABLE_REPORTS` | `False` | Whether to skip report generation |

> [!note]
> `SETTINGS` is a singleton — calling `get_settings()` from any module always returns the same instance with the same `RUN_ID`.

---

## 5. Prepare Input Data

The `data/` folder is **not part of the repository** — it is created automatically when you run the pipeline and is listed in `.gitignore`. The pipeline creates all subfolders it needs (`staging/`, `delivery/`, `reports/`) on the fly during execution.

All you need to do is:

1. **Create the `data/input/` folder** (if it doesn't exist yet)
2. **Drop your CSV files** into `data/input/`

File names must match the glob patterns in your registry files (e.g. `*sales*`, `*inventory*`). A typical naming convention includes the country prefix:

```
data/input/
├── FR_sales_data_202601.csv
├── US_sales_data_202601.csv
├── FR_inventory_data_202601.csv
└── US_inventory_data_202601.csv
```

The `data/static/mappings/product_mapping.csv` file is also required by the default pipeline (used by the `enrich_with_mapping` transformer).

### Quick Test with Generated Data

If you don't have real data yet, use the built-in test data generator to populate `data/input/` and `data/static/` with realistic sample files:

```bash
python test_files_generator/generator.py
```

This generates:
- **Sales CSV files** — multiple test cases (correct data, missing values, type errors, duplicates, out-of-range values, empty files)
- **Inventory CSV files** — with daily/weekly stock snapshots
- **Product mapping** — a `product_mapping.csv` in `data/static/mappings/`

> [!tip]
> The generator uses your `.env` settings (paths, CSV delimiter), so make sure `.env` is configured before running it.

---

## 6. Run the Pipeline

```bash
python main.py
```

This launches the Prefect flow with the default pipeline configuration:

1. **Raw Validation** — checks column presence, empty files, product ID validity
2. **Dispatch** — routes files into `SALES/`, `INVENTORY/` subfolders
3. **Transformation** — enriches with mappings, cleans strings, calculates fields
4. **Post-Transform Validation** — verifies the schema after transformation
5. **Cross-Validation** — checks null values, value ranges, data consistency
6. **Final Dispatch** — delivers files into region folders (`FR/`, `US/`)

> [!tip]
> The pipeline structure is fully configurable. You can add, remove, or reorder steps in `main.py`. See [[Pipeline Configuration]] for details.

### Output

After a successful run, find your outputs at:

```
data/delivery/<RUN_ID>/       # Final processed files
data/reports/<RUN_ID>/        # Validation and transformation reports
data/staging/<RUN_ID>/        # Intermediate step outputs
```

Where `<RUN_ID>` is the run timestamp (e.g. `20260324_185705`).

---

## 7. Check Reports

If any file fails validation or transformation, a plain-text report is written under `data/reports/<RUN_ID>/<step_name>/`. Each report lists all messages and pass/fail status per validator.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Invalid BACKEND_ENGINE` | `.env` missing or `BACKEND_ENGINE` not set to `polars` | Check `.env` |
| `NoInputFilesError` | No files in `data/input/` or previous step produced no output | Check input folder or registry patterns |
| `AllFilesFailedError` | Every file failed a step | Check reports in `data/reports/<RUN_ID>/` |
| `FileNotFoundError: product_mapping` | Missing static mapping file | Place `product_mapping.csv` in `data/static/mappings/` |

---

Next: [[Pipeline Configuration]] →
