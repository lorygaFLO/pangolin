"""Implementation of the `pangolin deploy` command.

Auto-discovers every pipeline in the current project's pipelines/ package
(see pangolin.cli._discovery) and registers + serves a Prefect deployment
for each. Ported from the old docker/deploy.py script so it stays in sync
with the library instead of being copied into every scaffolded project.

- Without a cron: the deployment is only triggered manually from the UI (Quick Run).
- To add a daily schedule to a pipeline, have it read its own env var (e.g.
  PANGOLIN_CRON) to build its module-level DEPLOYMENT_KWARGS.
"""

from __future__ import annotations

import importlib
import logging
import os
import time
from pathlib import Path

import typer

from pangolin.cli._discovery import load_pipelines

LOG = logging.getLogger("pangolin.deploy")


def _hydrate_from_prefect(manifest_path: Path, settings_block: str) -> None:
    """Pull Prefect Blocks and export them to os.environ.

    - JSON block named `settings_block`: every key/value becomes an env var.
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

    # 2) Prefect Variables whose names look like settings keys (UPPER_CASE)
    manifest_for_vars: dict = {}
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest_for_vars = yaml.safe_load(f) or {}
        except Exception:
            manifest_for_vars = {}
        for entry in manifest_for_vars.get("variables", []) or []:
            var_name = entry.get("name", "")
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

    # 3) Secret blocks listed in the manifest with expose_as_env
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
                LOG.info("Secret %r is empty; skipping export of %s", entry.get("name"), env_name)
                continue
            os.environ.setdefault(env_name, str(secret_value))
            LOG.info("env <- secret[%s] -> %s", entry["name"], env_name)
    else:
        LOG.info("No manifest found at %s; skipping secret hydration.", manifest_path)


def deploy(
    manifest: Path = typer.Option(
        None,
        "--manifest",
        envvar="PANGOLIN_MANIFEST",
        help="Prefect manifest YAML (default: docker/prefect_manifest.yaml).",
    ),
    settings_block: str = typer.Option(
        "pangolin-settings",
        "--settings-block",
        envvar="PANGOLIN_SETTINGS_BLOCK",
        help="Name of the Prefect JSON block holding settings overrides.",
    ),
) -> None:
    """Serve a Prefect deployment for every pipeline in the current project.

    Meant to run inside the deployment worker (e.g. the container started by
    the scaffolded docker-compose.yml, see `pangolin init --dockerization`).
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    os.environ.setdefault("PREFECT_LOGGING_EXTRA_LOGGERS", "pangolin")

    manifest_path = manifest or Path("docker/prefect_manifest.yaml")

    mode = os.getenv("PANGOLIN_MODE", "local").lower()
    LOG.info("PANGOLIN_MODE=%s", mode)
    LOG.info("Image build: GIT_BRANCH=%s GIT_SHA=%s", os.getenv("GIT_BRANCH", "?"), os.getenv("GIT_SHA", "?"))

    if mode in ("docker-local", "cloud"):
        _hydrate_from_prefect(manifest_path, settings_block)

    # Settings/env must be hydrated before pipelines (and pangolin.config.settings) import.
    pipelines = load_pipelines()

    from prefect import serve as prefect_serve

    base_tags = [t for t in (os.getenv("GIT_BRANCH"), os.getenv("GIT_SHA")) if t]

    deployments = []
    for pipeline_name, pipeline_flow in pipelines.items():
        module = importlib.import_module(f"pipelines.{pipeline_name}")
        deploy_kwargs = dict(getattr(module, "DEPLOYMENT_KWARGS", {}))
        extra_tags = deploy_kwargs.pop("extra_tags", [])
        kwargs: dict = {
            "name": getattr(module, "DEPLOYMENT_NAME", f"pangolin-{pipeline_name.replace('_', '-')}"),
            "tags": base_tags + extra_tags,
        }
        kwargs.update(deploy_kwargs)
        deployments.append(pipeline_flow.to_deployment(**kwargs))

    prefect_serve(*deployments)
