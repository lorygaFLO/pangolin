"""Generates the project-level README.md written by `pangolin init`.

Two things make this worth generating instead of shipping as a static
template file:

- The "core" settings table is introspected from `pangolin.config.settings.SETTINGS`
  at run time, so it can never drift out of sync with the library.
- The "folder" settings table is read from *this project's own*
  config/data_structure.yaml right after it's copied — those settings are
  not fixed: every project can declare a different set (see SETTINGS'
  `_resolve_paths`), so there is nothing to hardcode in a template.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _settings_reference_table() -> str:
    from pangolin.config.settings import SETTINGS

    lines = ["| Setting | Default | Description |", "| --- | --- | --- |"]
    for name, field in SETTINGS.model_fields.items():
        default = field.get_default(call_default_factory=True)
        if default is None:
            default_str = "*(none)*"
        elif default == "":
            default_str = "*(empty)*"
        else:
            default_str = f"`{default!r}`" if isinstance(default, str) else f"`{default}`"
        description = (field.description or "").replace("|", "\\|")
        lines.append(f"| `{name}` | {default_str} | {description} |")
    return "\n".join(lines)


def _folder_settings_table(structure_path: Path) -> str:
    """Mirrors SETTINGS._resolve_paths / _folder_names_from_data_structure:
    only top-level nodes of data_structure.yaml declaring `_settings_key`
    become folder settings."""
    with open(structure_path, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f) or {}
    rows = [
        (node["_settings_key"], key)
        for key, node in schema.items()
        if isinstance(node, dict) and "_settings_key" in node
    ]
    if not rows:
        return (
            "*(none declared yet — add `_settings_key: YOUR_ENV_VAR_NAME` to a "
            "top-level node in `config/data_structure.yaml` to add one)*"
        )
    lines = ["| Env var (settings key) | Folder name |", "| --- | --- |"]
    for settings_key, folder_name in rows:
        lines.append(f"| `{settings_key}` | `{folder_name}` |")
    return "\n".join(lines)


def render_readme(target: Path, dockerization: bool) -> str:
    """Build the README.md content for a freshly scaffolded project."""
    structure_path = target / "config" / "data_structure.yaml"

    if dockerization:
        docker_section = (
            "## Running it in Docker\n\n"
            "See [`docker/README.md`](docker/README.md) for the full Docker "
            "deployment stack (Prefect server + worker + bootstrap + reverse proxy).\n"
        )
    else:
        docker_section = (
            "## Running it in Docker\n\n"
            "Not scaffolded for this project. Re-run `pangolin init --dockerization` "
            "(or `-d`) in this same folder to add it — existing files are left untouched "
            "unless you also pass `--force`.\n"
        )

    return f"""\
# Project

Scaffolded by `pangolin init`. This file is generated once and is never
touched again by `pangolin init --force` if it already exists — edit it
freely.

## Mandatory setup (in order)

1. **`.env`** — fill in `BASEPATH`/`DATAPATH` for your machine (or your cloud
   container/prefix, if `FS_PROTOCOL` isn't `file`) and the IO options. See
   the settings reference below for every field pangolin reads.
2. **`config/data_structure.yaml`** — describe your project's folder layout.
   Every top-level node with a `_settings_key` becomes a setting you can
   override from `.env` (see "Folder settings" below). A step node under
   `staging` with `_pattern_matching: true` + `_registry: <path>` links it to
   one of the registry files below.
3. **`config/registries/*.yaml`** — one file per pipeline step: which
   validators/transformers run, matched by file-name glob pattern.
4. **`custom/`** — validators/transformers/processors specific to this
   project. Built-in ones ship with pangolin itself
   (`pangolin.utils.validators` / `pangolin.utils.transformers`) and don't
   need to be duplicated here.
5. **`pipelines/`** — one file per pipeline; each must expose a module-level
   `PIPELINE = <flow>`. See `pipelines/example_pipeline.py`.
6. *(optional)* **`custom/settings.py`** — need a setting of your own (e.g.
   `S.TRAINING_EPOCHS`)? Add a field to the `SETTINGS` class there. It's
   auto-detected by `get_settings()` — no library changes needed. See
   "Adding your own settings" below.

## Running it

```bash
pangolin list                      # discovered pipelines + their debuggable steps
pangolin run                       # run the default pipeline
pangolin step <pipeline> <step>    # run one step in isolation (needs DEBUG=True in .env)
pangolin restore <run_id>          # restore input from a previous backup
pangolin prefect-server            # persistent local Prefect server, isolated per project
pangolin deploy                    # serve every pipeline as a Prefect deployment
pangolin bootstrap                 # apply docker/prefect_manifest.yaml to a Prefect server
```

`pangolin restore` writes into a *fresh* RUN_ID's input folder, same as any
other run. Chaining it into `pangolin step <pipeline> <next_step>` to
reprocess that data is a separate CLI call with its own fresh RUN_ID by
default — set `DEBUG=True` in `.env` *before* running `restore` too, so
both calls agree on the same `DEBUG_RUN_ID` folder.

## Settings reference (`.env`)

Every field below can be set in `.env` or as an environment variable of the
same name. This table is generated from the pangolin version you have
installed — if it looks out of date, reinstall pangolin.

{_settings_reference_table()}

## Folder settings (from `config/data_structure.yaml`)

These are **not fixed** — every project declares its own, by giving a
top-level node in `config/data_structure.yaml` a `_settings_key`. This
project currently declares:

{_folder_settings_table(structure_path)}

## Adding your own settings

`S.TRAINING_EPOCHS`, `S.MY_API_KEY`, or anything else your own code needs
that isn't a folder and isn't one of pangolin's built-in fields above: add
it to the `SETTINGS` class in **`custom/settings.py`** (already scaffolded,
starts empty):

```python
class SETTINGS(_BaseSettings):
    TRAINING_EPOCHS: int = 10
```

`get_settings()` picks it up automatically — `S.TRAINING_EPOCHS` then works
anywhere in the project, read from `.env`/the environment exactly like the
built-in fields, with the same Pydantic validation. No changes to the
pangolin library needed. Delete `custom/settings.py` if you never need this.

{docker_section}"""
