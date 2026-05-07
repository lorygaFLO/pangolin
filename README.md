<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo_pangolin_dark.jpg">
    <source media="(prefers-color-scheme: light)" srcset="docs/assets/logo_pangolin.jpg">
    <img src="docs/assets/logo_pangolin.jpg" alt="Pangolin logo" style="width: 200px; aspect-ratio: 1; object-fit: cover; border-radius: 15px;"/>
  </picture>
</p>

# Pangolin — Data Ingestion, Validation & Transformation Pipeline

Pangolin is a flexible, modular data processing pipeline built on top of **Prefect** and **Polars**. It automates multi-stage ingestion, validation, transformation, and delivery of data files, ensuring data quality and compliance with user-defined rules at every step.

It is designed to be easy to ship and quick to set up, making it a good fit for personal projects or small/medium enterprise pipelines. If you routinely process and validate data from third-party sources, Pangolin gives you a declarative, YAML-driven approach to defining pipeline stages — no core code changes needed.

## Key Features

* **Prefect-orchestrated pipeline** with full observability and retry support
* **Declarative YAML registries** — define validation, transformation, and routing rules without writing Python
* **Polars backend** — fast, memory-efficient dataframe processing
* **fsspec integration** — swap local storage for S3, GCS, or Azure with a one-line config change
* **DataFacility** — YAML-driven data access layer mapping folder structure into a navigable Python object tree
* **Per-stage HTML reports** generated automatically for every processed file
* **Non-destructive processing** — input files are never modified; each stage writes to its own staging folder
* **Extensible with decorators** — add validators/transformers with `@register_validator` / `@register_transformer`

## Project Structure

```
├── main.py                          # Pipeline entry point (Prefect flows)
├── example.env                      # Environment variable template
├── pyproject.toml                   # Project metadata & dependencies
├── config/
│   ├── settings.py                  # Settings loader (reads .env, builds paths)
│   ├── constants.py                 # System-wide constants
│   ├── data_structure.yaml          # Declarative folder/file schema (DataFacility)
│   └── registries/                  # YAML-driven stage configuration
│       ├── 0_raw_validation.yaml
│       ├── 1_dispatcher.yaml
│       ├── 2_transform_registry.yaml
│       ├── 3_validation.yaml
│       ├── 4_cross_validation.yaml
│       └── 5_dispatcher.yaml
├── engine/
│   ├── DataFacility.py              # YAML-driven data access layer
│   ├── reporter.py                  # Report generation
│   ├── core/
│   │   ├── exceptions.py            # Custom pipeline exceptions
│   │   └── logger.py                # Per-processor logger
│   └── processors/
│       ├── BaseProcessor.py         # Shared processor base class
│       ├── DataValidator.py         # Validation processor
│       ├── DataTranformer.py        # Transformation processor
│       └── FileDispatcher.py        # File routing processor
├── utils/
│   ├── validators.py                # Built-in validator functions
│   ├── transformers.py              # Built-in transformer functions
│   └── fs_wrapper.py                # fsspec filesystem wrapper
├── docker/
│   └── deploy.py                    # Prefect deployment script
├── data/
│   ├── input/                       # Drop input files here
│   ├── staging/                     # Per-run intermediate data
│   ├── delivery/                    # Final outputs (timestamped)
│   └── reports/                     # Pipeline reports (timestamped)
└── docs/
    └── doumentation-obsidian/       # Full documentation (Obsidian vault)
```

## Quick Start

```bash
pip install -e .
```

1. Copy `example.env` to `.env` and fill in the values
2. Place input files in `data/input/`
3. Run the pipeline:

```bash
python main.py
```

## Documentation

Full documentation is available in the [`docs/doumentation-obsidian/`](docs/doumentation-obsidian/) folder. It is structured as an [Obsidian](https://obsidian.md/) vault — open the folder in Obsidian for the best reading experience (linked pages, graph view, etc.).

| Guide | Description |
|-------|-------------|
| [Welcome](docs/documentation-obsidian/Welcome.md) | Introduction and overview |
| [Getting Started](docs/documentation-obsidian/Getting%20Started.md) | Installation, configuration, and first run |
| [Architecture Overview](docs/documentation-obsidian/Architecture%20Overview.md) | Pipeline stages, directory structure, and data flow |
| [Pipeline Configuration](docs/documentation-obsidian/Pipeline%20Configuration.md) | Registry files and YAML-driven stage configuration |
| [Registry Reference](docs/documentation-obsidian/Registry%20Reference.md) | Detailed reference for all registry formats |
| [Data Structure & DataFacility](docs/documentation-obsidian/Data%20Structure%20&%20DataFacility.md) | YAML-driven filesystem mapping |
| [Writing Validators](docs/documentation-obsidian/Writing%20Validators.md) | How to create custom validation functions |
| [Writing Transformers](docs/documentation-obsidian/Writing%20Transformers.md) | How to create custom transformation functions |
| [Creating a New Processor](docs/documentation-obsidian/Creating%20a%20New%20Processor.md) | Extending the engine with new processor types |

## Contributing

Contributions are welcome! Priority areas:

* **Dockerization** *(in progress)*
* **Full Prefect Integration** (deployment manifests, work pools, artifacts, notifications)
* **New File Format Support** (Excel, JSON, etc.)
* **Additional Validators/Transformers**
* **Cloud Storage** (S3/GCS/Azure documentation and examples)



## Running in Docker

Pangolin ships a 4-service Docker stack (Prefect server, one-shot bootstrap,
worker running `flow.serve()`, Caddy reverse proxy) plus an idempotent
manifest-driven configuration system.

### The three modes

`PANGOLIN_MODE` selects how settings are loaded:

| Mode | Settings source | Where it runs |
|------|-----------------|---------------|
| `local` | Pydantic reads `.env` directly | Host machine, no Docker |
| `docker-local` | Pulled from Prefect **Variables + Blocks** at flow start; `data/` bind-mounted | Local Docker |
| `cloud` | Same as `docker-local` but with real cloud creds; UI on `${PUBLIC_HOSTNAME}` | VM / cloud host |

`docker-local` is intentionally identical to `cloud` so you can rehearse the
production flow on your laptop.

### Quick start (docker-local)

On macOS / Linux / Git Bash / WSL:

```bash
cp docker/.env.docker.example docker/.env.docker
# edit docker/.env.docker if you need (defaults work out-of-the-box)

git checkout develop          # or any branch you want baked in
make build                    # captures branch + short SHA into the image
make up                       # starts server, bootstrap, worker, caddy
make logs                     # follow logs
```

On Windows PowerShell (no `make` required) use the bundled helper:

```powershell
Copy-Item docker\.env.docker.example docker\.env.docker
git checkout develop
.\make.ps1 build
.\make.ps1 up
.\make.ps1 logs
```

`make.ps1` exposes the same targets as the `Makefile`
(`build`, `up`, `down`, `restart`, `logs`, `ps`, `bootstrap`, `shell`,
`clean`, `nuke`).

UI URLs (both work, no `/etc/hosts` edits required):

- http://localhost:8080
- http://pangolin.localhost:8080  ← uses `PROJECT_NAME` from `docker/.env.docker`

Change the host port via `PROXY_PORT` in `docker/.env.docker` (also update
`PREFECT_UI_API_URL` to match, otherwise the UI's API calls will hit the
wrong port).

### Building for a specific branch

The image records which Git branch/SHA it was built from (baked in as
`ENV GIT_BRANCH` / `ENV GIT_SHA`, logged at worker startup, and exposed in
the Prefect UI as Variables `pangolin_git_branch` and `pangolin_git_sha`).

```bash
git checkout my-feature-branch
make build       # auto-fills --build-arg GIT_BRANCH / GIT_SHA from the working copy
make up
```

Docker itself does **not** check out branches — that's your job; the image
just records what it was built from.

### The manifest (`docker/prefect_manifest.yaml`)

Single source of truth for everything Pangolin expects in Prefect. Three
value sources:

- inline literal — used as-is
- `"${ENV_VAR}"` — resolved from container env (provided via `docker/.env.docker`)
- `null` / `""` — created **empty** so you can fill it via the UI; if a
  non-empty value already exists on the server, it is preserved on rerun

The bootstrap container applies the manifest on every `make up` and is fully
idempotent — re-running never wipes user-edited values.

### Bulk-creating empty blocks/variables

When you know you'll need a bunch of secrets but don't have the values yet:

```bash
# from the host
make bootstrap                                          # apply current manifest

# inside the worker container (or any pangolin image)
docker compose --env-file docker/.env.docker run --rm bootstrap \
    python docker/bootstrap_prefect.py create-empty \
    --type secret --name foo --name bar --name baz

docker compose --env-file docker/.env.docker run --rm bootstrap \
    python docker/bootstrap_prefect.py create-empty \
    --type variable --from-file names.txt
```

Each new entry is appended to `docker/prefect_manifest.yaml` with `value: null`, so
it survives image rebuilds. Then fill the values in the Prefect UI.

### Going from `docker-local` to `cloud`

Edit `docker/.env.docker`:

```dotenv
PANGOLIN_MODE=cloud
PUBLIC_HOSTNAME=pangolin.example.com
PREFECT_UI_API_URL=http://pangolin.example.com/api
AZURE_STORAGE_CONNECTION_STRING=<the real value>
# ...any other secrets referenced by ${...} in the manifest
```

Then `make build && make up` on the VM. The same Caddyfile picks up
`PUBLIC_HOSTNAME` and serves the UI there.

> The reverse proxy currently has **no authentication**. There's a TODO in
> `Caddyfile` showing where to plug `basicauth` once you want to lock the UI
> down.

### What's where

| File | Purpose |
|------|---------|
| `docker/Dockerfile` | App image, captures `GIT_BRANCH` / `GIT_SHA` build args |
| `docker-compose.yml` | 4-service stack, named volume for the Prefect DB |
| `docker/Caddyfile` | Reverse proxy: `localhost`, `<PROJECT_NAME>.localhost`, `${PUBLIC_HOSTNAME}` |
| `docker/bootstrap_prefect.py` | Idempotent manifest applier + `create-empty` CLI |
| `docker/prefect_manifest.yaml` | Declarative list of Variables/Blocks (commit-safe) |
| `docker/.env.docker.example` | Template for `.env.docker` (real secrets live here, not in git) |
| `docker/requirements-docker.txt` | UTF-8 dependency list used by the image |
| `Makefile` | `build`, `up`, `down`, `logs`, `bootstrap`, `shell`, `clean` |
| `docker/deploy.py` | `flow.serve()` entry point; hydrates env from Prefect before importing `main` |

