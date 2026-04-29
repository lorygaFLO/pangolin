# Future Developments

This page collects planned improvements and extensions to Pangolin. Items are grouped by theme and ordered roughly by priority, but none of them are committed to a timeline.

---

## 1. Testing Strategy

**Current state:** No automated test suite exists. The only way to verify the pipeline is to run it end-to-end against the sample files in `data/input/`.

**Goal:** Cover the three layers of the stack independently so regressions are caught fast and cheaply.

### Unit tests — utils layer

Each function in `utils/validators.py` and `utils/transformers.py` is a pure (or near-pure) function that maps a Polars `DataFrame` to a result. These are ideal candidates for unit tests:

- Parametrize with small, hand-crafted `pl.DataFrame` fixtures that cover the happy path, edge cases, and expected failure modes.
- Assert on the returned value (boolean flags, transformed frame, raised exceptions).
- No filesystem, no Prefect, no YAML needed.

### Integration tests — processor layer

Each `Processor` subclass (`Validator`, `DataTransformer`, `FileDispatcher`) reads a registry YAML and works on files. Integration tests should:

- Use `tmp_path` (pytest fixture) to create an isolated input/output/staging directory tree.
- Supply a minimal registry YAML tailored to the test.
- Run `processor.execute()` and assert on the files written to the output folder and on the report produced.
- Keep Prefect out of the picture by calling `processor.execute()` directly (no `@flow` context required).

### End-to-end tests — pipeline layer

A small set of E2E tests that spin up the full Prefect flow against a known input dataset and assert on the final delivery output. These are slower and should be kept few:

- Use `data/input/` test files already present in the repository (the `case*` files).
- Run via `pytest` with a dedicated marker (`@pytest.mark.e2e`) so they can be excluded from fast CI runs.
- Assert both on delivered file content and on the absence of error reports.

### Tooling

| Tool | Role |
|------|------|
| `pytest` | Test runner |
| `pytest-cov` | Coverage reporting |
| `polars` (in-memory frames) | Fixture data, no CSV files needed at unit level |
| `tmp_path` (pytest built-in) | Isolated filesystem per test |

A `tests/` folder at project root with the structure below is the target layout:

```
tests/
├── conftest.py               # shared fixtures (tmp data dir, sample DataFrames)
├── unit/
│   ├── test_validators.py
│   └── test_transformers.py
└── integration/
    ├── test_validator_processor.py
    ├── test_transformer_processor.py
    └── test_dispatcher_processor.py
```

---

## 2. Cloud Environments & Docker

**Current state:** All I/O is local. `fsspec` is already a dependency and `FSWrapper` abstracts filesystem calls, so the groundwork exists — but the pipeline has never been tested against a remote backend, and there is no container image.

**Goal:** Make it possible to run Pangolin against cloud storage (S3, Azure Blob, GCS) from inside a Docker container, while keeping the local development experience unchanged.

### 2a. Cloud storage via fsspec

`fsspec` already supports `s3://`, `az://`, and `gcs://` URI schemes transparently. The work needed is:

- Extend `config/settings.py` to accept a `FILESYSTEM_PROTOCOL` env variable (`local` | `s3` | `az` | `gcs`) and cloud-specific credentials.
- Thread the resolved `fsspec` filesystem instance through `FSWrapper` instead of hard-coding `LocalFileSystem`.
- Ensure `data_structure.yaml` paths stay relative so the same YAML works both locally and in the cloud (the base URI is injected at runtime from settings).
- Validate that the `DataFacility` read/write helpers continue to work through an `AbstractFileSystem` interface.

No changes to processors, registries, or user-facing pipeline code should be required.

### 2b. Docker image

A `Dockerfile` at project root targeting a production-grade image:

- Base image: `python:3.12-slim`.
- Install dependencies from `pyproject.toml` in a separate layer (leverages Docker build cache).
- Copy source code; do **not** copy `data/` or `.env` (both are mounted at runtime or injected via environment variables).
- Entry point: `docker/deploy.py` (the existing Prefect serve script).

A `docker-compose.yml` for local testing with a bind-mounted `data/` folder so the container reads and writes to the host filesystem — preserving the ability to inspect staging and delivery files locally without changing any pipeline code.

### 2c. Secrets and configuration via Prefect Blocks and Variables

Rather than relying solely on `.env` files or raw OS environment variables, secrets and runtime configuration should be stored and retrieved through **Prefect Blocks** and **Prefect Variables**. This applies consistently across local, Docker, and cloud environments:

- **Prefect Variables** — for non-sensitive configuration values (e.g., `FILESYSTEM_PROTOCOL`, output format, CSV delimiter). Variables are stored in the Prefect server/cloud and are accessible from any flow run without injecting environment variables manually.
- **Prefect Blocks** — for sensitive credentials (e.g., S3 access keys, Azure connection strings, GCS service account JSON). Blocks are encrypted at rest, versioned, and can be rotated without touching code or redeploying the image. Example block types: `S3Bucket`, `AzureBlobStorageCredentials`, `GcpCredentials`.

The target pattern in `config/settings.py` should fall back gracefully:

```
1. Prefect Block / Variable  (preferred in all deployed environments)
2. OS environment variable   (fallback for local runs without a Prefect server)
3. .env file                 (development convenience only, never committed)
```

This means the Docker image carries no secrets at build time, and local development without a Prefect server continues to work via `.env` as today.

### 2d. Local testability is preserved

The `FILESYSTEM_PROTOCOL=local` default means running `python main.py` without Docker continues to work exactly as today. Cloud paths are only activated by environment variable (or Prefect Variable), so:

- All unit and integration tests run locally without any cloud credentials.
- The E2E test suite can optionally target a cloud bucket by overriding settings — no code changes needed.

---

## 3. Enhanced Example — Unified Dataset Pipeline

**Current state:** The default example treats every input file independently all the way to delivery. Each file is validated, transformed, and dispatched in isolation. This is useful, but it only demonstrates one shape of pipeline — and it limits the downstream possibilities to per-file operations.

**Goal:** Introduce a second pipeline shape where the first meaningful step is to **consolidate all input files into a single unified dataset**. Once you have one dataset, the rest of the pipeline operates at scale on the whole picture, and the kinds of processors you can build become far more varied depending on your need.

### Why this matters

The consolidation step is not an end in itself — it is an *enabler*. A unified dataset unlocks an entirely different class of downstream processors:

- **Predictive models** — train or score an ML model on the full dataset (e.g., demand forecasting, anomaly detection, churn prediction).
- **Aggregated reporting** — produce cross-region, cross-period summaries that are impossible when files are kept separate.
- **BI-ready data model** — join and reshape the unified dataset into a star or flat schema ready to be consumed directly by a BI dashboard (Power BI, Tableau, Metabase, etc.), replacing manual report preparation.
- **Any custom processor you want to build** — the architecture imposes no constraint on what a processor does once the data is unified.

The imagination is the only limit on what downstream steps can do.

### The pattern

```
Multiple input files
        │
        ▼
  ┌─────────────────────────────────────┐
  │  0 ─ Raw Validation                 │  validate each file individually
  │  1 ─ Consolidation                  │  ← concat / join → one dataset
  │  2 ─ (anything)                     │  ML, reporting, enrichment, …
  │  3 ─ Post-Processing Validation     │  validate the unified output
  │  4 ─ Final Delivery                 │  deliver result(s)
  └─────────────────────────────────────┘
```

Step 1 receives, for example, `FR_sales_data.csv` and `US_sales_data.csv` and writes a single `all_sales.parquet`. Every step after that sees only one file and can reason about the full picture.

### What to implement

A more comprehensive example that walks future users through the full journey: consolidating multiple input files into one dataset and then building something meaningful on top of it. The example should be concrete enough to serve as a reference starting point for anyone who wants to extend Pangolin beyond per-file processing.

---

## 4. Better Use of Prefect

**Current state:** Prefect is used primarily as a flow runner and logger. The richer orchestration features it provides — tasks, artifacts, caching, concurrency, notifications — are largely unused.

**Goal:** Progressively adopt Prefect features that add observability and resilience without complicating the local development experience.

### 4a. `@task` decoration for fine-grained tracking

Today every processor exposes a single `execute()` method wrapped in a `@flow`. Breaking `execute()` into Prefect `@task`s (e.g., `load_registry`, `process_file`, `write_report`) would give:

- Per-file task states visible in the Prefect UI.
- Automatic retry on transient I/O failures (`retries=2`).
- Task-level run history without re-running the whole flow.

### 4b. Artifacts for reports

Prefect 3 supports markdown and table artifacts that appear directly in the UI. Each processor already generates a textual report; surfacing it as a Prefect artifact would make it visible in the flow run page without having to open the reports folder.

```python
from prefect.artifacts import create_markdown_artifact

create_markdown_artifact(
    key="validation-report",
    markdown=report_content,
    description="Raw validation results"
)
```

### 4c. Caching expensive tasks

Steps that are deterministic and expensive (e.g., a heavy transformation on a file that has not changed) can be cached using Prefect's `cache_key_fn` and `cache_expiration`. This is particularly valuable in iterative development where only one stage changes between runs.

### 4d. Concurrent file processing

Currently files are processed sequentially inside each processor. Wrapping per-file processing in `@task` and submitting them via a `TaskRunner` (e.g., `ConcurrentTaskRunner`) would allow independent files to be processed in parallel, cutting wall-clock time for large batches.

### 4e. Notifications on failure

Prefect supports sending alerts (Slack, email, PagerDuty) when a flow run fails or transitions to a crashed state. A simple notification block configured in the Prefect UI (or via code) would make operational monitoring practical without requiring a separate monitoring stack.

### 4f. Scheduled deployments

The `docker/deploy.py` script already supports a `PANGOLIN_CRON` env variable. The next step is documenting and testing a full deployment cycle: build the Docker image, push to a registry, create a Prefect work pool, and deploy with a schedule. This ties together items 2 and 4 into an end-to-end production setup.
