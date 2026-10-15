# Container deployment (engine: __ENGINE__)

Four services (see `docker-compose.yml`). `docker-compose.yml`/`Dockerfile` are
plain OCI/Compose-spec files — Docker and Podman both read them unchanged;
only the `make`/`make.ps1` invocation below is pinned to the engine chosen at
`pangolin init --engine`. For Podman, make sure a compose provider is
installed (`podman-compose`, or Podman >= 4.7's built-in `podman compose`).

> [!warning] Podman on Windows/WSL2
> Starting this stack with Podman on a Windows/WSL2 machine may fail with
> `netavark: nftables error ... Could not process rule: No such file or
> directory` — a known, still-open WSL2 kernel limitation (NAT/masquerade
> support for `nftables` isn't compiled in; see
> [microsoft/WSL#9772](https://github.com/microsoft/WSL/issues/9772)), not a
> bug in this scaffold. It does not affect real Linux hosts. The Podman path
> has only been validated statically so far — **test end-to-end on an actual
> Linux environment** before relying on it in production; on Windows, use
> Docker Desktop instead.

| Service | What it does |
| --- | --- |
| `prefect-server` | Prefect 3 server + UI, persistent SQLite on a volume |
| `bootstrap` | One-shot, idempotent — runs `pangolin bootstrap` to create/update Prefect Variables and Blocks from `docker/prefect_manifest.yaml`. Safe to re-run. |
| `worker` | Runs `pangolin deploy` — serves every pipeline in `pipelines/` as a Prefect deployment. |
| `caddy` | Reverse proxy in front of the Prefect UI/API. |

## Setup

1. Copy `docker/.env.docker.example` to `docker/.env.docker` and fill it in
   (do **not** commit `.env.docker` — it may hold real secrets).
2. Fill `docker/prefect_manifest.yaml` — Variables and Blocks to seed the
   Prefect server with on bootstrap. Anything written as `${ENV_VAR}` is
   resolved from `docker/.env.docker` at bootstrap time; `null` creates an
   empty placeholder you fill in later from the Prefect UI.
3. `make build && make up`

## Reaching the UI

The Prefect UI is **not** exposed directly on the `prefect-server` container
(no host port mapping) — it's reachable through the Caddy reverse proxy:

- `http://localhost:${PROXY_PORT:-8080}`
- `http://${PROJECT_NAME:-pangolin}.localhost:${PROXY_PORT:-8080}`

Both variables come from `docker/.env.docker`. For a public deployment, set
`PUBLIC_HOSTNAME` there instead (see the comments in `docker/Caddyfile`).

`make up` ends by printing the address (`Prefect UI: http://localhost:8080`),
taken from `PREFECT_UI_URL` in `docker/.env.docker`. The worker uses the same
value for the "View at ..." links in its logs, so keep it matching the port /
public hostname.

## Other Makefile targets

```bash
make logs        # tail logs from all services
make ps           # service status
make restart      # restart the worker only
make bootstrap    # re-run the one-shot bootstrap (idempotent)
make shell        # shell into the worker container
make down         # stop the stack (keeps volumes)
make clean        # stop the stack AND drop volumes (wipes the Prefect DB)
```

## Image tags and pinned versions

The project image is tagged `pangolin:<branch>`, with the branch made
tag-safe (`feature/x` → `pangolin:feature-x`); `make` / `make.ps1` compute it
as `IMAGE_TAG`. Plain `docker compose` falls back to `pangolin:local`.

All images are pinned to exact versions (Python base in `docker/Dockerfile`;
`prefecthq/prefect` and `caddy` in `docker-compose.yml`). Keep the Prefect
server tag aligned with the `prefect==` pin of the pangolin library the image
installs, and bump versions deliberately.

## Project dependencies

Everything pangolin needs (Prefect, polars, ...) comes with the library. If
your `custom/` or `pipelines/` code imports anything else (e.g. `yfinance`),
list it — exact versions — in `docker/requirements.txt`; the Dockerfile
installs that file into the image. Without it the worker fails at startup on
`ModuleNotFoundError`, because `pangolin deploy` imports every pipeline.

- No `-e ../pangolin` / local paths: the image is built from this folder only.
- It is separate from the `requirements.txt` you may use for local
  development — keep the two in sync.
- The dependency layer is cached and does **not** depend on the git branch/SHA,
  so a new commit doesn't reinstall your packages; editing the file does.

## Telemetry

Prefect sends "anonymous" usage statistics to a third party (Amplitude) by
default. This stack opts out (`PREFECT_SERVER_ANALYTICS_ENABLED=false` on
`prefect-server`, `DO_NOT_TRACK=1` on `bootstrap`/`worker`), so it stays fully
self-hosted once the images are built.

## One image, built once

`bootstrap` and `worker` share one image and only `worker` builds it
(both have `pull_policy: never`: the image exists only locally, never on a
registry); two services building the same tag in parallel could fail with
`image ... already exists`. Build first (`make build`)
— `make bootstrap` alone needs the image to exist already.

## Updating the pangolin version baked into the image

`docker/Dockerfile` installs the `pangolin` library itself via
`PANGOLIN_INSTALL_SPEC` (defaults to git, pinned to `PANGOLIN_REF=main`,
since pangolin isn't published to PyPI/a private index yet). Override at
build time, e.g.:

```bash
__ENGINE__ compose build --build-arg PANGOLIN_REF=v0.3.0
```

Once pangolin is published, switch `PANGOLIN_INSTALL_SPEC` in the Dockerfile
to a plain version pin instead.

That install layer is cached: with a floating ref like `PANGOLIN_REF=main`, a
plain rebuild keeps the pangolin version already in the image. To pick up new
commits of the ref, rebuild without cache (`__ENGINE__ compose --env-file
docker/.env.docker build --no-cache`), or pin `PANGOLIN_REF` to a tag/commit
for reproducible builds.
