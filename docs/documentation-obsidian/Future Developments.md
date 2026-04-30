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

