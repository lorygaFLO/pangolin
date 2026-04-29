"""
Registers the data_pipeline as a Prefect deployment and serves it.

Modes (selected via PANGOLIN_MODE):
  - local        : Pydantic reads .env directly (no Prefect hydration).
  - docker-local : settings/secrets are pulled from Prefect Blocks and
                   exported into os.environ BEFORE main is imported, so
                   Pydantic-Settings picks them up transparently.
  - cloud        : same as docker-local.

Schedule:
  - Without PANGOLIN_CRON: deployment is manual-only (Quick Run from UI).
  - With PANGOLIN_CRON   : also runs on the given cron (UTC).
"""

import logging
import os
import sys
import time
from pathlib import Path

# Ensure the project root (parent of this file's directory) is on sys.path
# so that `main`, `engine`, `config`, etc. are importable regardless of
# where this script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LOG = logging.getLogger("pangolin.deploy")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---------------------------------------------------------------------------
# Settings hydration (must run BEFORE `from main import data_pipeline`,
# because main.py does `from config.settings import *` at import time).
# ---------------------------------------------------------------------------

def _hydrate_from_prefect() -> None:
    """Pull Prefect Blocks and export them to os.environ.

    - JSON block named `pangolin-settings`: every key/value becomes an env var.
    - Every Secret block whose manifest entry has `expose_as_env: <NAME>` is
      exported under that env var name.
    """
    import yaml
    try:
        from prefect.blocks.system import JSON, Secret
    except ImportError:
        try:
            from prefect.blocks.core import JSON, Secret
        except ImportError:
            from prefect.blocks.system import Secret
            from prefect.blocks.core import Block
            class JSON(Block):
                _block_type_slug = "json"
                value: dict = {}

    manifest_path = Path(os.getenv("PANGOLIN_MANIFEST", "docker/prefect_manifest.yaml"))
    if not manifest_path.exists():
        alt = Path(__file__).resolve().parent / "prefect_manifest.yaml"
        if alt.exists():
            manifest_path = alt

    settings_block = os.getenv("PANGOLIN_SETTINGS_BLOCK", "pangolin-settings")

    # Wait briefly for the API (worker may start the same second as the server)
    api_url = os.getenv("PREFECT_API_URL")
    if api_url:
        import httpx
        deadline = time.monotonic() + 60.0
        while time.monotonic() < deadline:
            try:
                if httpx.get(api_url.rstrip("/") + "/health", timeout=3.0).status_code < 500:
                    break
            except Exception:
                pass
            time.sleep(2.0)

    # 1) JSON settings block
    try:
        block = JSON.load(settings_block)
        payload = block.value or {}
        if isinstance(payload, dict):
            for key, value in payload.items():
                if value is None or value == "":
                    continue
                os.environ.setdefault(str(key), str(value))
                LOG.info("env <- block[%s].%s", settings_block, key)
        else:
            LOG.warning("Block %r is not a JSON object", settings_block)
    except Exception as exc:
        LOG.warning("Could not load JSON block %r: %s", settings_block, exc)

    # 2) Prefect Variables whose names match SETTINGS fields (UPPER_CASE names)
    #    Only variables with ALL-CAPS names are treated as settings env vars.
    try:
        from prefect.variables import Variable
        all_vars = Variable.get.__func__  # existence check only
    except Exception:
        pass
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest_for_vars = yaml.safe_load(f) or {}
        except Exception:
            manifest_for_vars = {}
        for entry in manifest_for_vars.get("variables", []) or []:
            var_name = entry.get("name", "")
            # Only export variables whose name looks like a settings key (UPPER_CASE)
            if not var_name.isupper():
                continue
            try:
                from prefect.variables import Variable
                value = Variable.get(var_name)
                if value not in (None, ""):
                    os.environ.setdefault(var_name, str(value))
                    LOG.info("env <- variable[%s]", var_name)
            except Exception as exc:
                LOG.warning("Could not load Variable %r: %s", var_name, exc)

    # 4) Secret blocks listed in the manifest with expose_as_env
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest = yaml.safe_load(f) or {}
        except Exception as exc:
            LOG.warning("Could not read manifest %s: %s", manifest_path, exc)
            manifest = {}
        for entry in manifest.get("blocks", []) or []:
            if entry.get("type", "json").lower() != "secret":
                continue
            env_name = entry.get("expose_as_env")
            if not env_name:
                continue
            try:
                secret_value = Secret.load(entry["name"]).get()
            except Exception as exc:
                LOG.warning("Could not load Secret %r: %s", entry.get("name"), exc)
                continue
            if secret_value in (None, ""):
                LOG.info("Secret %r is empty; skipping export of %s",
                         entry.get("name"), env_name)
                continue
            os.environ.setdefault(env_name, str(secret_value))
            LOG.info("env <- secret[%s] -> %s", entry["name"], env_name)
    else:
        LOG.info("No manifest found at %s; skipping secret hydration.", manifest_path)


# Make sure pangolin logs flow into Prefect
os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin")

_MODE = os.getenv("PANGOLIN_MODE", "local").lower()
LOG.info("PANGOLIN_MODE=%s", _MODE)
LOG.info("Image build: GIT_BRANCH=%s GIT_SHA=%s",
         os.getenv("GIT_BRANCH", "?"), os.getenv("GIT_SHA", "?"))

if _MODE in ("docker-local", "cloud"):
    _hydrate_from_prefect()


# Now it is safe to import the flow (which imports SETTINGS).
from main import data_pipeline, generate_test_data  # noqa: E402

CRON_SCHEDULE = os.getenv("PANGOLIN_CRON") or None

if __name__ == "__main__":
    from prefect import serve as prefect_serve

    tags = [t for t in (os.getenv("GIT_BRANCH"), os.getenv("GIT_SHA")) if t]

    pipeline_deploy_kwargs: dict = {
        "name": "pangolin-daily",
        "tags": tags,
    }
    # Prefect 3.6+ rejects cron=None; only pass it when set.
    if CRON_SCHEDULE:
        pipeline_deploy_kwargs["cron"] = CRON_SCHEDULE

    generate_deploy_kwargs: dict = {
        "name": "pangolin-generate-test-data",
        "tags": tags + ["test-data"],
    }

    # Serve both deployments in the same process
    prefect_serve(
        data_pipeline.to_deployment(**pipeline_deploy_kwargs),
        generate_test_data.to_deployment(**generate_deploy_kwargs),
    )
