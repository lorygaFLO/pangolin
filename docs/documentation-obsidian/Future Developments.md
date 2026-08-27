# Future Developments

Planned improvements. No committed timeline.

---

## 1. Testing Strategy

Add a `tests/` folder covering three layers:

- **Unit** — pure functions in `pangolin/utils/validators.py` and `pangolin/utils/transformers.py`, parametrized with in-memory `pl.DataFrame` fixtures. No filesystem, no Prefect.
- **Integration** — each `Processor` subclass run via `processor.execute()` against a `tmp_path` directory and a minimal registry YAML.
- **End-to-end** — full Prefect flow against the existing `data/input/case*` files, gated behind a `@pytest.mark.e2e` marker.

---

## 2. Cloud Environments & Docker — Refinements

The Docker stack and cloud-mode infrastructure are implemented in this version. However, the setup (Dockerfile, docker-compose, bootstrap, deploy scripts) is for the most part AI-generated and has not been battle-tested in production. Refinements and enhancements are expected — treat it as a working starting point, not a hardened deployment.

Areas that likely need attention:

- **Real cloud testing** — the `cloud` mode has only been exercised in `docker-local`. A deployment to an actual VM or cloud service is needed to validate networking, secrets, volume mounts, and scheduling end-to-end. Not possible at the moment. **Contributions and collaboration are very welcome here** — if you have access to a cloud environment and want to help validate or extend this, please open an issue or reach out.
- **Cloud storage** — `FSWrapper` currently only supports the local filesystem. Extend it to accept a `FILESYSTEM_PROTOCOL` env variable (`local` | `s3` | `az` | `gcs`), threading the right `fsspec` filesystem through without touching processors or registries.
- **Docker image hardening** — review layer caching, multi-stage builds, non-root user, image size optimization.


---

## 3. Enhanced Example — Unified Dataset Pipeline

The clearest way to demonstrate that Pangolin is a battle-ready foundation is a richer end-to-end example. Add a second pipeline shape (as an alternative or addition to the `pangolin init` scaffold's `example_pipeline.py`) that consolidates multiple input files into one unified dataset and then builds something meaningful on top: demand forecasting, a BI-ready star schema, an anomaly detection report. The goal is to give anyone running `pangolin init` a concrete, production-shaped starting point they can adapt rather than build from scratch.

---

## 4. Better Use of Prefect
- **Artifacts** — for example, surface processor reports as Prefect markdown artifacts directly in the flow run page.
- **Concurrency** — submit per-file tasks via `ConcurrentTaskRunner` to process batches in parallel.
- **Notifications** — configure a Prefect notification block for Slack/email alerts on flow failure.
- **Scheduled deployments** — document the full cycle: build image → push → create work pool → deploy with `PANGOLIN_CRON`.

---

## 5. OpenLineage for Data & Event Lineage

Lineage today is implicit (the `lineage` list on each `Batch`, plus reports/logs). Explore adopting [OpenLineage](https://openlineage.io/) to emit standardized lineage events across runs and pipelines, giving a queryable, visualizable trail of how datasets flow through the dispatcher/validation/transform steps — and potentially generalizing beyond data lineage to broader event/decision tracing (routing, cross-validation outcomes, etc.). Also expose a simple way for users to emit their own custom lineage/event messages from within a processor, rather than being limited to the built-in ones.

---

## 6. Scalability Across Data Scales

Pangolin is currently exercised mostly against small-to-medium files that fit comfortably in memory via Polars. Investigate how the engine behaves and should adapt as data volumes grow — from lightweight local runs up to large, high-throughput datasets — so the same pipeline shape scales gracefully instead of requiring a rewrite (e.g. lazy/streaming evaluation, chunked/batched processing, partitioned reads and writes).

---

## 7. More Built-in Processors, Validators & Transformers

Grow the built-in library in `pangolin/engine/processors`, `pangolin/utils/validators.py`, and `pangolin/utils/transformers.py` so more pipelines can be assembled from registry configuration alone, without writing custom code. Fewer gaps to fill means a smoother experience for anyone adapting Pangolin to a new use case.

---

## 8. Backend-Agnostic DataFrame Engine (Narwhals)

Pangolin is hard-wired to Polars. Explore adopting [Narwhals](https://narwhals-dev.github.io/narwhals/) or another generalization layer as a compatibility layer so users could pick another backend (e.g. DuckDB, Spark) without rewriting processors, validators, and transformers.

---

## 9. Data Contract Standard for Validation

Evaluate using the [Data Contract](https://datacontract.com/) standard to drive validation, instead of (or alongside) the current registry-based validators.

---

## 10. Extensible DataFacility Behaviors

Every `_`-prefixed key's **value** in `data_structure.yaml` is already fully user-editable (it's the project's own file), and any key not in the reserved list is already exposed generically as `node.<key>` for custom code to read. What's *not* extensible today is the **automatic behavior** those reserved keys trigger (`_versioned`, `_timestamped`, `_required`, and file-format inference/read/write) — it's hard-coded in `DataNode`/`DataFacility` (`src/pangolin/engine/DataFacility.py`), so a project can't add a new self-acting key (e.g. `_compress: gzip` to transparently gzip on write) without forking the library. Same class of gap `custom/settings.py` closed for `SETTINGS` — DataFacility has no equivalent extension point yet.

Two directions, increasing in scope:

- **Custom format registry** — a `@register_format(name, reader=..., writer=...)` decorator (same pattern as `@register_validator`/`@register_transformer`), consulted by `_infer_format`/`read()`/`write()` before falling back to the built-in csv/parquet/excel/json/yaml map. Solves "pangolin doesn't know this file format" without touching the library.
- **Subclassable `DataFacility`** via a scaffolded `custom/data_facility.py`, auto-detected by `get_project_data()` the same way `get_settings()` already auto-detects `custom/settings.py` (see [[Adding Custom Settings]] for the pattern this would mirror). Lets a project override `_resolve_path`/`read`/`write` for its own needs.
- **(Further out)** A hook registry keyed by custom `_`-attributes (`@register_write_hook("compress")` triggered by `_compress: gzip` on a node) — the most direct answer to "make behavior-inducing attributes pluggable," but needs the lifecycle hook points (path resolution, pre/post read, pre/post write) designed properly first. Would likely fall out naturally once a project can subclass `DataFacility` and start writing its own hook dispatch for its own needs.

---

## 11. Configuration UI

A graphical interface for managing project configuration — including registries — instead of editing files directly. Deferred for now: file-based configuration is easier to version, review, and iterate on while the project is still under active development, and there's no established user base yet that would benefit from a GUI. Worth revisiting once the configuration surface stabilizes and a real need emerges.

