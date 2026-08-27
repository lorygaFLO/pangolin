"""Implementation of the `pangolin bootstrap` command group.

Idempotent Prefect bootstrap utility, ported from the old
docker/bootstrap_prefect.py script so it stays in sync with the library
instead of being copied into every scaffolded project.

- Waits for the Prefect API to be healthy.
- Reads a manifest YAML (path via --manifest / PANGOLIN_MANIFEST, default
  docker/prefect_manifest.yaml in the current project).
- Creates / updates Prefect Variables and Blocks (json / secret).
- Resolves three value sources:
    * inline literal
    * "${ENV_VAR}" placeholder -> from the container/host env (missing => empty)
    * null / "" -> created empty (or left untouched if a non-empty value
      already exists on the server, so user-edits via the UI are preserved).
- `pangolin bootstrap create-empty` bulk-creates empty blocks/variables and
  appends them to the manifest.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any, List, Optional

import httpx
import typer
import yaml
from prefect.variables import Variable

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

LOG = logging.getLogger("pangolin.bootstrap")

DEFAULT_MANIFEST = Path("docker/prefect_manifest.yaml")
ENV_REF_RE = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)\}$")

bootstrap_app = typer.Typer(
    name="bootstrap",
    help="Apply the Prefect manifest (Variables/Blocks) to the current project's Prefect server.",
    invoke_without_command=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def wait_for_api(timeout: float = 120.0, interval: float = 2.0) -> None:
    """Block until the Prefect API answers /health, or raise."""
    api_url = os.getenv("PREFECT_API_URL")
    if not api_url:
        raise RuntimeError("PREFECT_API_URL is not set")
    health_url = api_url.rstrip("/") + "/health"
    deadline = time.monotonic() + timeout
    last_err: Optional[Exception] = None
    LOG.info("Waiting for Prefect API at %s ...", health_url)
    while time.monotonic() < deadline:
        try:
            r = httpx.get(health_url, timeout=5.0)
            if r.status_code < 500:
                LOG.info("Prefect API is healthy.")
                return
        except Exception as exc:
            last_err = exc
        time.sleep(interval)
    raise RuntimeError(f"Prefect API not healthy after {timeout}s: {last_err}")


def _resolve_value(raw: Any) -> Any:
    """Resolve ${ENV_VAR} placeholders. Returns the resolved value or None
    if the value is null / empty / unresolved."""
    if raw is None:
        return None
    if isinstance(raw, str):
        m = ENV_REF_RE.match(raw.strip())
        if m:
            env_name = m.group(1)
            val = os.getenv(env_name)
            return val if val not in (None, "") else None
        return raw if raw != "" else None
    if isinstance(raw, dict):
        return {k: _resolve_value(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return [_resolve_value(v) for v in raw]
    return raw


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (dict, list)) and len(value) == 0:
        return True
    return False


def _existing_block_value(block_type: str, name: str) -> Any:
    try:
        if block_type == "json":
            return JSON.load(name).value
        if block_type == "secret":
            return Secret.load(name).get()
    except Exception:
        return None
    return None


def _existing_variable_value(name: str) -> Any:
    try:
        return Variable.get(name)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------

def load_manifest(path: Path) -> dict:
    if not path.exists():
        LOG.warning("Manifest %s not found; using empty manifest.", path)
        return {"variables": [], "blocks": []}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("variables", [])
    data.setdefault("blocks", [])
    return data


def save_manifest(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    LOG.info("Manifest written: %s", path)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def apply_variable(entry: dict) -> None:
    name = entry["name"]
    resolved = _resolve_value(entry.get("value"))

    if _is_empty(resolved):
        existing = _existing_variable_value(name)
        if not _is_empty(existing):
            LOG.info("Variable %r kept (manifest empty, server has value).", name)
            return
        Variable.set(name, "", overwrite=True)
        LOG.info("Variable %r created empty.", name)
        return

    Variable.set(name, resolved, overwrite=True)
    LOG.info("Variable %r set from manifest.", name)


def apply_block(entry: dict) -> None:
    name = entry["name"]
    btype = entry.get("type", "json").lower()
    resolved = _resolve_value(entry.get("value"))
    expose_as = entry.get("expose_as_env")

    if btype not in ("json", "secret"):
        raise ValueError(f"Unsupported block type {btype!r} for {name!r}")

    if _is_empty(resolved):
        existing = _existing_block_value(btype, name)
        if not _is_empty(existing):
            LOG.info("Block %r (%s) kept (manifest empty, server has value).", name, btype)
        else:
            empty_value = {} if btype == "json" else ""
            if btype == "json":
                JSON(value=empty_value).save(name, overwrite=True)
            else:
                Secret(value=empty_value).save(name, overwrite=True)
            LOG.info("Block %r (%s) created empty.", name, btype)
    else:
        if btype == "json":
            if not isinstance(resolved, dict):
                raise ValueError(f"JSON block {name!r} requires a mapping value")
            JSON(value=resolved).save(name, overwrite=True)
        else:
            Secret(value=str(resolved)).save(name, overwrite=True)
        LOG.info("Block %r (%s) set from manifest.", name, btype)

    if expose_as:
        # informational only; `pangolin deploy` is what actually exports it at worker startup
        LOG.info("  (will be exposed as env var %s at worker startup)", expose_as)


def _run_bootstrap(manifest_path: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    wait_for_api()
    manifest = load_manifest(manifest_path)

    # Surface the build identity into Prefect Variables so the UI shows it.
    branch = os.getenv("GIT_BRANCH")
    sha = os.getenv("GIT_SHA")
    if branch:
        Variable.set("pangolin_git_branch", branch, overwrite=True)
        LOG.info("Variable 'pangolin_git_branch' = %s", branch)
    if sha:
        Variable.set("pangolin_git_sha", sha, overwrite=True)
        LOG.info("Variable 'pangolin_git_sha' = %s", sha)

    for entry in manifest.get("variables", []):
        try:
            apply_variable(entry)
        except Exception as exc:
            LOG.error("Failed to apply variable %r: %s", entry.get("name"), exc)
            raise typer.Exit(code=2)

    for entry in manifest.get("blocks", []):
        try:
            apply_block(entry)
        except Exception as exc:
            LOG.error("Failed to apply block %r: %s", entry.get("name"), exc)
            raise typer.Exit(code=2)

    LOG.info("Bootstrap completed successfully.")


_MANIFEST_OPTION = typer.Option(
    DEFAULT_MANIFEST,
    "--manifest",
    envvar="PANGOLIN_MANIFEST",
    help="Manifest YAML path.",
)


@bootstrap_app.callback(invoke_without_command=True)
def bootstrap(
    ctx: typer.Context,
    manifest: Path = _MANIFEST_OPTION,
) -> None:
    """Apply the manifest to Prefect (default when no subcommand is given)."""
    if ctx.invoked_subcommand is not None:
        return
    _run_bootstrap(manifest)


@bootstrap_app.command("create-empty")
def create_empty(
    type: str = typer.Option(..., "--type", help="secret | json | variable"),
    name: Optional[List[str]] = typer.Option(
        None, "--name", help="Name to create. Repeat the flag for multiple."
    ),
    from_file: Optional[Path] = typer.Option(
        None, "--from-file", help="Text file with one name per line (# comments allowed)."
    ),
    manifest: Path = _MANIFEST_OPTION,
) -> None:
    """Bulk-create empty blocks/variables and append them to the manifest."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if type not in ("secret", "json", "variable"):
        typer.secho(f"Invalid --type {type!r}: must be secret, json or variable.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    wait_for_api()

    names: List[str] = list(name or [])
    if from_file:
        with open(from_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    names.append(line)
    seen = set()
    names = [n for n in names if not (n in seen or seen.add(n))]

    if not names:
        typer.secho("No names provided. Use --name or --from-file.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    manifest_data = load_manifest(manifest)
    section = "variables" if type == "variable" else "blocks"
    existing_names = {e["name"] for e in manifest_data.get(section, [])}

    for n in names:
        if n not in existing_names:
            entry: dict = {"name": n, "value": None}
            if type != "variable":
                entry["type"] = type
            manifest_data[section].append(entry)
            existing_names.add(n)
            LOG.info("Manifest: appended %s %r (empty).", type, n)
        else:
            LOG.info("Manifest: %s %r already present, leaving as-is.", type, n)

        if type == "variable":
            apply_variable({"name": n, "value": None})
        else:
            apply_block({"name": n, "type": type, "value": None})

    save_manifest(manifest, manifest_data)
