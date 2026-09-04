# Getting Started

This guide walks you through installing Pangolin, scaffolding a project, and running the example pipeline for the first time.

---

## Quickstart — Use Pangolin as a Library

Pangolin is an installable package with a CLI. To start a brand-new project you don't need to clone this repo — a project lives in its **own** folder/repo, separate from the pangolin library:

```bash
pip install git+https://github.com/lorygaFLO/pangolin.git
mkdir my-project && cd my-project
pangolin init                     # scaffolds config/, custom/, pipelines/, data/, README.md
pangolin run                      # runs the bundled, fully working example pipeline
```

`pangolin init` generates a complete example: an example pipeline (backup → raw validation → transform → custom audit processor → delivery dispatch), custom validator/transformer stubs, filled-in registries, and a sample CSV in `data/input/`. It also writes a **`README.md`** in the new project listing the mandatory setup steps and a settings reference table generated live from your installed pangolin version — read that first, it's the authoritative reference for whatever version you have installed (this guide covers the concepts, that file covers the exact fields).

Pass `--dockerization` (or `-d`) to also scaffold the Docker deployment stack:

```bash
pangolin init my-project -d
```

See [[Docker Deployment]] for that flow.

Other commands:

```bash
pangolin list                      # discovered pipelines + their debuggable steps
pangolin step <pipeline> <step>    # run a single step in isolation (debugging)
pangolin restore <run_id>          # restore input from a previous backup
pangolin deploy                    # serve every pipeline as a Prefect deployment
pangolin bootstrap                 # apply docker/prefect_manifest.yaml to a Prefect server
pangolin --version                 # show the installed pangolin version
```

The rest of this guide covers the concepts in more depth. The last section covers working on the **pangolin library itself** (this repository).

---

## Prerequisites

- **Python 3.10+**
- **pip** (or your preferred package manager)

---

## Configuring `.env`

`pangolin init` writes a starter `.env`. Open it and set the values for your machine:

```ini
# Project identity. Change per project — namespaces this project's local
# Prefect state away from every other pangolin project on this machine.
# See "Running via the Prefect UI" below.
PROJECT_NAME=my-project

# Backend engine (only "polars" is supported)
BACKEND_ENGINE=polars

# Filesystem protocol ("file" for local, "s3", "gcs", "az" for cloud)
FS_PROTOCOL=file

# Base path to your project
BASEPATH=C:\path\to\my-project

# Path to the data folder (absolute, or relative to BASEPATH)
DATAPATH=C:\path\to\my-project\data

# Set to True to skip report generation
DISABLE_REPORTS=False

# CSV settings
CSV_DELIMITER=;

# Output format for processed files: "csv" or "parquet"
OUTPUT_FORMAT=parquet
```

Folder-name settings (`INPUT_FOLDER_NAME`, `STAGING_FOLDER_NAME`, ...) are **not fixed** — every project declares its own by adding a `_settings_key` to a top-level node in `config/data_structure.yaml`. The example project ships with `INPUT_FOLDER_NAME`, `STAGING_FOLDER_NAME`, `DELIVERY_FOLDER_NAME`, `REPORTS_FOLDER_NAME`, `BACKUP_FOLDER_NAME`. Your generated project's `README.md` lists the exact set for your `data_structure.yaml`, and the full field list (with defaults and descriptions) for every core setting. See [[Data Structure & DataFacility]] for how `_settings_key` works.

> [!tip]
> On Linux/macOS, use forward slashes for paths. On Windows, both `\` and `/` work.

### Cloud Storage (Optional)

To use S3, GCS, or Azure Blob instead of local disk:

```ini
FS_PROTOCOL=s3
FS_OPTIONS={"key": "AKIAIOSFODNN7EXAMPLE", "secret": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"}
```

`FS_OPTIONS` accepts a JSON string with any `fsspec` storage options for the chosen protocol.

> [!important] Install the cloud driver first
> `fsspec` does **not** bundle cloud backends — you must install the relevant package before switching protocol:
>
> | Protocol | Package to install |
> |---|---|
> | `s3` (AWS S3) | `pip install s3fs` |
> | `az` (Azure Blob) | `pip install adlfs` |
> | `gcs` (Google Cloud Storage) | `pip install gcsfs` |
>
> For **Docker deployments**, add a `RUN pip install <package>` line to your project's `docker/Dockerfile` (after the `pip install "pangolin @ ..."` line) and rebuild the image.

---

## Settings: What's Fixed vs. What's Yours

`SETTINGS` (in `pangolin.config.settings`, part of the library) is a `pydantic-settings` `BaseSettings` class with two kinds of fields:

- **Core fields** — `BASEPATH`, `DATAPATH`, `BACKEND_ENGINE`, `CSV_DELIMITER`, `OUTPUT_FORMAT`, `DEBUG`, `FS_PROTOCOL`, `FS_OPTIONS`, etc. Fixed, declared once in the library, the same across every project — because pangolin's own engine (`DataFacility`, `FSWrapper`, `BaseProcessor`) reads them directly to do its job. Your project's generated `README.md` has the full table.
- **Folder fields** — `INPUT_FOLDER_NAME`, `STAGING_FOLDER_NAME`, and whatever else you declare. **Not fixed** — one per top-level node in *your* `config/data_structure.yaml` that has a `_settings_key`, resolved dynamically by the engine. Two projects can have entirely different folder settings.

You do **not** edit `pangolin.config.settings` for normal usage — it lives inside the installed `pangolin` package now, not in your project. A project-specific setting your own code needs (`TRAINING_EPOCHS`, an API key, a feature flag) — something only *your* code reads, not pangolin's engine — goes in **`custom/settings.py`** instead, scaffolded empty by `pangolin init`. See [[Adding Custom Settings]] for the full guide (adding fields, validation, computed fields).

Access settings anywhere in your code:

```python
from pangolin.config.settings import get_settings
S = get_settings()
print(S.BASEPATH, S.INPUT_FOLDER_NAME)
```

> [!note]
> `get_settings()` returns a **fresh instance** each time — it holds static config from `.env`. The `RUN_ID` is **not** part of `SETTINGS`; it belongs to `RunContext`, instantiated once per run (via `get_run_context()`) in the main flow and passed down to every subflow and processor. This keeps per-run state separate from environment configuration.

`RunContext` is user-extensible the same way `SETTINGS` is: a project-specific per-run field goes in **`custom/run_context.py`**, scaffolded empty by `pangolin init`. Get an instance with `get_run_context()` instead of instantiating `RunContext()` directly — it auto-detects your subclass, same pattern as `get_settings()`.

| Property | Example | Description |
| --- | --- | --- |
| `CTX.RUN_ID` | `"20260324_185705"` | Unique timestamp for the current run — lives on `RunContext` |
| `CTX.GIT_BRANCH` | `"develop"` | Git branch the code was run from — env var `GIT_BRANCH` (baked into Docker images) if set, else read from the local working tree |
| `CTX.GIT_SHA` | `"4f38b25"` / `"4f38b25-dirty"` | Short commit SHA, same resolution as `GIT_BRANCH`; `-dirty` suffix when the local working tree has uncommitted changes |
| `CTX.summary()` | `"RUN_ID: ... \| branch: ... \| commit: ..."` | Convenience one-liner for logging at pipeline start |
| `S.BASEPATH` / `S.DATAPATH` | `Path(...)` | Absolute paths, resolved at startup |
| `S.PATH_REPORTS` | `Path(...)` | Computed: `DATAPATH / REPORTS_FOLDER_NAME` |

---

## Prepare Input Data

The `data/` folder is **not part of your project's repo** — `pangolin init` creates it on disk (git-ignored). The pipeline creates all subfolders it needs (`staging/`, `delivery/`, `reports/`) on the fly during execution.

`pangolin init` already drops a sample CSV into `data/input/` so the example pipeline runs immediately. To add your own files, drop them into `data/input/` — file names must match the glob patterns in your registry files (e.g. `*sales*`).

### Quick Test with Generated Data

The example project doesn't ship a synthetic-data generator by default (that was specific to an earlier example pipeline in this repo's history). If you need one, write a small pipeline under `pipelines/` that produces sample files into `data/input/` and register it like any other pipeline — see [[Pipeline Configuration]].

---

## Run the Pipeline

```bash
pangolin run
```

This launches the Prefect flow for the example pipeline:

1. **Backup** — copies current input to `backup/<RUN_ID>/`
2. **Raw Validation** — checks column presence, empty files
3. **Transform** — calculates fields, adds an ingestion timestamp
4. **Audit** (custom processor) — counts nulls per file, demonstrates extending the engine beyond the three built-in processor types
5. **Delivery Dispatch** — delivers files into `delivery/<RUN_ID>/`

> [!tip]
> The pipeline structure is fully configurable. Add, remove, or reorder steps in `pipelines/example_pipeline.py`, or add a whole new pipeline under `pipelines/`. See [[Pipeline Configuration]] for details.

### Running via the Prefect UI (persistent server)

`pangolin run` executes the flow once, directly, in the foreground. If you instead want to trigger runs from the **Prefect dashboard** (Quick Run, schedules, run history), you need a persistent Prefect server plus the deployments served — two terminals:

> [!warning] Isolate each project's Prefect state
> Prefect defaults to one global state directory (`~/.prefect`, one shared SQLite DB) for every project on your machine. If two pangolin projects both use that default, they land in the **same** database — their deployments, runs and logs all show up mixed together in the same dashboard.
>
> `pangolin run` / `pangolin deploy` / `pangolin bootstrap` already avoid this automatically: they derive `PREFECT_HOME` from `PROJECT_NAME` in `.env` (see [[Getting Started#Configuring .env|Configuring .env]]) before touching Prefect. Use `pangolin prefect-server` below (not the bare `prefect server start`) so Terminal 1 gets the same guarantee — pangolin can't inject env vars into a process it doesn't launch.

**Terminal 1 — start the Prefect server**

```bash
pangolin prefect-server
```

A thin wrapper around `prefect server start` — same flags work (e.g. `pangolin prefect-server --host 0.0.0.0 --port 4201`) — that first derives `PREFECT_HOME` exactly like `pangolin run`/`deploy` do. Prints the `PREFECT_HOME` it's using on startup. Leave this running. The dashboard is now available at `http://127.0.0.1:4200`.

> [!tip]
> Still want the bare Prefect command? `export PREFECT_HOME="$(pwd)/.prefect/my-project"` (match `PROJECT_NAME` from `.env`; PowerShell: `$env:PREFECT_HOME = "..."`) before `prefect server start` gets you the same isolation by hand.

**Terminal 2 — serve the deployments**

```bash
export PREFECT_API_URL="http://127.0.0.1:4200/api"   # PowerShell: $env:PREFECT_API_URL = "..."
pangolin deploy
```

> [!important]
> Without `PREFECT_API_URL` pointing at the server from Terminal 1, `pangolin deploy` spins up its own **temporary, throwaway** Prefect server instead of using the persistent one — your deployments won't show up in the dashboard from Terminal 1.

`pangolin deploy` auto-discovers every pipeline under `pipelines/` and registers a deployment for each — by default **Example Pipeline** (`pangolin-example-pipeline`) — then polls for scheduled/manual runs. Trigger it from the dashboard (**Deployments → Quick Run**) or via CLI:

```bash
prefect deployment run "Example Pipeline/pangolin-example-pipeline"
```

### Output

After a successful run, find your outputs at:

```
data/delivery/<RUN_ID>/       # Final processed files
data/reports/<RUN_ID>/        # Validation and transformation reports
data/staging/<RUN_ID>/        # Intermediate step outputs
```

Where `<RUN_ID>` is the run timestamp (e.g. `20260324_185705`).

---

## Check Reports

If any file fails validation or transformation, a plain-text report is written under `data/reports/<RUN_ID>/<step_name>/`. Each report lists all messages and pass/fail status per validator.

---

## Troubleshooting

| Symptom                              | Cause                                                         | Fix                                                    |
| ------------------------------------ | ------------------------------------------------------------- | ------------------------------------------------------ |
| `Invalid BACKEND_ENGINE`             | `.env` missing or `BACKEND_ENGINE` not set to `polars`        | Check `.env`                                           |
| `NoInputFilesError`                  | No files in `data/input/` or previous step produced no output | Check input folder or registry patterns                |
| `AllFilesFailedError`                | Every file failed a step                                      | Check reports in `data/reports/<RUN_ID>/`              |
| `No pipelines/ package found`        | `pangolin run`/`list`/`step` run outside a project root       | `cd` into the project folder (the one with `pipelines/`) |

> [!tip]
> Need to test or debug a single step in isolation (e.g. from the debugger) instead of the whole pipeline? See **Debugging a Single Step** in [[Pipeline Configuration]].

---

## Working on the Pangolin Library Itself (this repo)

The sections above are for using pangolin as a dependency in your own project. To contribute to the library (`src/pangolin/`) instead:

```bash
git clone https://github.com/lorygaFLO/pangolin.git
cd pangolin
python -m venv .venv
.venv\Scripts\Activate.ps1   # Linux/macOS: source .venv/bin/activate
pip install -e .
```

This installs pangolin in **editable** mode — changes to `src/pangolin/**.py` are picked up immediately by anything using it, no reinstall needed (reinstall only when `pyproject.toml` itself changes: new dependency, new `[project.scripts]` entry, new top-level package). There is no runnable project in this repo — to exercise the engine end-to-end while developing, scaffold a throwaway project alongside it:

```bash
pangolin init ../pangolin-sandbox
cd ../pangolin-sandbox
pangolin run
```

Edit library code in `pangolin/`, re-run `pangolin run` from the sandbox — no reinstall in between.

---

Next: [[Pipeline Configuration]] →
