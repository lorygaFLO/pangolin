"""
Idempotent Prefect bootstrap utility.

- Waits for the Prefect API to be healthy.
- Reads a manifest YAML (path via env PANGOLIN_MANIFEST, default
  ./prefect_manifest.yaml).
- Creates / updates Prefect Variables and Blocks (json / secret).
- Resolves three value sources:
    * inline literal
    * "${ENV_VAR}" placeholder -> from container env (missing => treated as empty)
    * null / "" -> created empty (or left untouched if a non-empty value
      already exists on the server, so user-edits via UI are preserved).
- Also exposes a `create-empty` CLI to bulk-create empty blocks/variables
  and append them to the manifest.

Usage:
    python bootstrap_prefect.py                        # one-shot bootstrap
    python bootstrap_prefect.py bootstrap              # same as above
    python bootstrap_prefect.py create-empty --type secret --name foo --name bar
    python bootstrap_prefect.py create-empty --type variable --from-file names.txt
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import httpx
import yaml
from prefect.variables import Variable

# Prefect 3.x renamed/moved the JSON block across minor releases.
try:
    from prefect.blocks.system import JSON, Secret
except ImportError:
    try:
        from prefect.blocks.core import JSON, Secret
    except ImportError:
        from prefect.blocks.system import Secret
        # Last resort: build a thin wrapper around the generic Block API
        from prefect.blocks.core import Block
        class JSON(Block):
            _block_type_slug = "json"
            value: dict = {}

LOG = logging.getLogger("pangolin.bootstrap")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_MANIFEST = Path(os.getenv("PANGOLIN_MANIFEST", "docker/prefect_manifest.yaml"))
ENV_REF_RE = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)\}$")


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
    last_err: Exception | None = None
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
    """Return the current value of a block, or None if it does not exist."""
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
    raw = entry.get("value")
    resolved = _resolve_value(raw)

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
    raw = entry.get("value")
    resolved = _resolve_value(raw)
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
        # informational only; deploy.py is what actually exports it at flow start
        LOG.info("  (will be exposed as env var %s at worker startup)", expose_as)


def cmd_bootstrap(manifest_path: Path) -> int:
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
            return 2

    for entry in manifest.get("blocks", []):
        try:
            apply_block(entry)
        except Exception as exc:
            LOG.error("Failed to apply block %r: %s", entry.get("name"), exc)
            return 2

    LOG.info("Bootstrap completed successfully.")
    return 0


# ---------------------------------------------------------------------------
# create-empty CLI
# ---------------------------------------------------------------------------

def _read_names(args) -> list[str]:
    names: list[str] = list(args.name or [])
    if args.from_file:
        with open(args.from_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    names.append(line)
    # de-dupe, preserve order
    seen = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def cmd_create_empty(args, manifest_path: Path) -> int:
    wait_for_api()
    names = _read_names(args)
    if not names:
        LOG.error("No names provided. Use --name or --from-file.")
        return 1

    manifest = load_manifest(manifest_path)
    section = "variables" if args.type == "variable" else "blocks"
    existing_names = {e["name"] for e in manifest.get(section, [])}

    for name in names:
        # Append to manifest with null value if not already present
        if name not in existing_names:
            entry: dict[str, Any] = {"name": name, "value": None}
            if args.type != "variable":
                entry["type"] = args.type
            manifest[section].append(entry)
            existing_names.add(name)
            LOG.info("Manifest: appended %s %r (empty).", args.type, name)
        else:
            LOG.info("Manifest: %s %r already present, leaving as-is.", args.type, name)

        # Create / ensure-exists in Prefect (won't overwrite a non-empty value)
        if args.type == "variable":
            apply_variable({"name": name, "value": None})
        else:
            apply_block({"name": name, "type": args.type, "value": None})

    save_manifest(manifest_path, manifest)
    return 0


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bootstrap_prefect", description=__doc__)
    p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST,
                   help=f"Manifest path (default: {DEFAULT_MANIFEST})")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("bootstrap", help="Apply the manifest to Prefect (default).")

    ce = sub.add_parser("create-empty", help="Bulk-create empty blocks/variables.")
    ce.add_argument("--type", choices=["secret", "json", "variable"], required=True)
    ce.add_argument("--name", action="append",
                    help="Name to create. Repeat flag for multiple.")
    ce.add_argument("--from-file", type=Path,
                    help="Text file with one name per line (# comments allowed).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cmd = args.command or "bootstrap"
    if cmd == "bootstrap":
        return cmd_bootstrap(args.manifest)
    if cmd == "create-empty":
        return cmd_create_empty(args, args.manifest)
    LOG.error("Unknown command: %s", cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
