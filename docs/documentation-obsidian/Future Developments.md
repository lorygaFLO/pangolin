# Future Developments

Planned improvements. No committed timeline.

---

## 1. Testing Strategy

Add a `tests/` folder covering three layers:

- **Unit** — pure functions in `utils/validators.py` and `utils/transformers.py`, parametrized with in-memory `pl.DataFrame` fixtures. No filesystem, no Prefect.
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

The clearest way to demonstrate that Pangolin is a battle-ready template is a richer end-to-end example. Add a second pipeline shape that consolidates multiple input files into one unified dataset and then builds something meaningful on top: demand forecasting, a BI-ready star schema, an anomaly detection report. The goal is to give anyone who forks the repo a concrete, production-shaped starting point they can adapt rather than build from scratch. 

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

Grow the built-in library in `engine/processors`, `utils/validators.py`, and `utils/transformers.py` so more pipelines can be assembled from registry configuration alone, without writing custom code. Fewer gaps to fill means a smoother experience for anyone adapting Pangolin to a new use case.

---

## 8. Backend-Agnostic DataFrame Engine (Narwhals)

Pangolin is hard-wired to Polars. Explore adopting [Narwhals](https://narwhals-dev.github.io/narwhals/) or another generalization layer as a compatibility layer so users could pick another backend (e.g. DuckDB, Spark) without rewriting processors, validators, and transformers.



