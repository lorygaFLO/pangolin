# Docker Deployment

> [!warning] AI-Generated
> This Docker setup (Dockerfile, docker-compose, bootstrap, deploy scripts) is for the most part AI-generated and has not been battle-tested in production. It likely requires refinements — treat it as a working starting point, not a hardened deployment.

This guide covers running Pangolin inside Docker using the bundled 4-service stack (Prefect server, bootstrap, worker, reverse proxy).

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running (whale icon steady in the system tray)
- Git (to capture the branch name at build time)

---

## Concepts in 30 Seconds

| Term | Meaning |
|---|---|
| **Image** | A frozen snapshot of the OS + code + dependencies. Built once with `make build`. |
| **Container** | A running instance of an image. Started with `make up`, stopped with `make down`. |
| **Volume** | A folder that survives container restarts (used for the Prefect database). |
| **Compose** | A YAML file (`docker-compose.yml`) that describes several containers that start together. |

---

## The Three Modes

Set `PANGOLIN_MODE` in `docker/.env.docker` to choose how settings are loaded:

| Mode | Where it runs | How settings are loaded |
|---|---|---|
| `local` | Host machine, no Docker | Pydantic reads `.env` directly — same as before Dockerization |
| `docker-local` | Local Docker | Settings pulled from Prefect Variables + Blocks at flow start; `data/` bind-mounted from host |
| `cloud` | VM / cloud server | Identical to `docker-local` but with real credentials and a public hostname |

`docker-local` exists so you can rehearse the full cloud flow on your laptop before deploying.

---

## The Four Services

```
Browser ──► http://localhost:8080
                  │
            ┌─────▼──────┐
            │   caddy    │  Reverse proxy (routes traffic)
            └─────┬──────┘
                  │
            ┌─────▼──────────┐
            │ prefect-server │  Dashboard + API  (DB on named volume)
            └──┬─────────┬───┘
               │         │
        ┌──────▼──┐  ┌───▼──────┐
        │bootstrap│  │  worker  │
        │(exits   │  │(always   │
        │ on done)│  │ running) │
        └─────────┘  └──────────┘
                      ▲
                      │ bind-mount
                 ./data/  ◄── your CSV files
```

1. **prefect-server** — Hosts the Prefect UI and API. Persists run history on the `prefect-data` volume.
2. **bootstrap** — One-shot: reads `docker/prefect_manifest.yaml`, creates/updates Blocks and Variables in Prefect, then exits (exit code 0 = success).
3. **worker** — Waits for bootstrap to finish, then runs `docker/deploy.py` which calls `data_pipeline.serve()` and polls for scheduled or manual runs.
4. **caddy** — Lightweight reverse proxy. Exposes the UI on `localhost:8080` and `<PROJECT_NAME>.localhost:8080` without any `/etc/hosts` edits (modern browsers resolve `*.localhost` to `127.0.0.1` automatically).

---

## Quick Start — docker-local (your laptop)

**Windows PowerShell:**

```powershell
Copy-Item docker\.env.docker.example docker\.env.docker
# edit docker\.env.docker if needed — defaults work out of the box
git checkout develop          # or whichever branch you want baked in
.\make.ps1 build              # builds the image (~2 min first time)
.\make.ps1 up                 # starts all 4 containers
.\make.ps1 logs               # follow logs (Ctrl+C to stop tailing)
```

**Linux / macOS / Git Bash:**

```bash
cp docker/.env.docker.example docker/.env.docker
git checkout develop
make build
make up
make logs
```

Open the UI at:
- http://localhost:8080
- http://pangolin.localhost:8080

Go to **Deployments → Full Processing Pipeline / pangolin-daily → Quick Run** to trigger the pipeline manually.

---

## Quick Start — cloud (server / VM)

1. **On your machine** — build and push the image to a registry (e.g. GitHub Container Registry, Docker Hub, Azure ACR):

```powershell
git checkout main
.\make.ps1 build
docker tag pangolin:main ghcr.io/your-org/pangolin:main
docker push ghcr.io/your-org/pangolin:main
```

2. **On the server** — copy only these three files (no need for the whole repo):

```
docker-compose.yml
docker/Caddyfile
docker/.env.docker        ← create this directly on the server
```

3. **On the server** — create `docker/.env.docker` with the real values (only 3 lines differ from docker-local):

```dotenv
PANGOLIN_MODE=cloud
PROJECT_NAME=pangolin
PUBLIC_HOSTNAME=pangolin.mycompany.com
PREFECT_UI_API_URL=http://pangolin.mycompany.com/api
PROXY_PORT=80
# Real secrets:
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
```

4. **On the server** — start the stack:

```bash
docker compose --env-file docker/.env.docker up -d
```

The UI will be reachable at `http://pangolin.mycompany.com`. No code changes needed compared to docker-local.

> To add **HTTPS** (automatic certificate via Let's Encrypt), change `docker/Caddyfile` from `http://{$PUBLIC_HOSTNAME}` to just `{$PUBLIC_HOSTNAME}`. Requires port 443 open on the server and DNS pointing to it.

---

## Daily Commands

| Command | What it does |
|---|---|
| `.\make.ps1 up` | Start all containers |
| `.\make.ps1 down` | Stop containers (Prefect DB preserved) |
| `.\make.ps1 logs` | Tail logs in real time (Ctrl+C exits tailing only) |
| `.\make.ps1 ps` | Show container states |
| `.\make.ps1 restart` | Restart only the worker (after code changes) |
| `.\make.ps1 bootstrap` | Re-apply the manifest (idempotent, safe to re-run) |
| `.\make.ps1 build` | Rebuild the image |
| `.\make.ps1 clean` | Stop + **wipe the Prefect DB** |
| `.\make.ps1 nuke` | `clean` + remove the pangolin image |

---

## Branch-Aware Builds

The image records which Git branch and commit SHA it was built from. They are:
- Baked into the image as `ENV GIT_BRANCH` / `ENV GIT_SHA`
- Logged at worker startup
- Exposed in the Prefect UI as Variables `pangolin_git_branch` / `pangolin_git_sha`

```powershell
git checkout my-feature-branch
.\make.ps1 build   # auto-captures branch + SHA
.\make.ps1 up
```

Docker does **not** check out branches itself — you do that; the image just records what it was built from.

---

## Configuration: `docker/prefect_manifest.yaml`

Single source of truth for everything Pangolin expects in Prefect. Three value sources:

| Syntax | Meaning |
|---|---|
| `value: input` | Inline literal — used as-is on every bootstrap |
| `value: "${ENV_VAR}"` | Resolved from container env (from `docker/.env.docker`) |
| `value: null` | Created empty — user fills it via the Prefect UI |

**Idempotency rule:** if the manifest entry is `null` and a non-empty value already exists in Prefect (e.g. edited via UI), bootstrap leaves it untouched. Your UI edits survive rebuilds.

This file is **safe to commit to git** — it contains no plaintext secrets, only `${VAR}` references or `null`.

---

## Secrets and `docker/.env.docker`

`docker/.env.docker` is the only file that contains real secret values. It must **not** be committed to git (add it to `.gitignore`). Use `docker/.env.docker.example` as the template.

Lifecycle of a secret (e.g. `AZURE_STORAGE_CONNECTION_STRING`):

```
First run
  docker/.env.docker  →  bootstrap reads env  →  stores encrypted in Prefect DB
                                                          │
                                          User edits via UI → new value in Prefect DB
                                          (docker/.env.docker no longer needed for that field)

After clean (DB wiped)
  docker/.env.docker  →  bootstrap re-seeds from scratch
```

---

## ⚠️ Security Warning — No User Management

> **Pangolin currently has no user authentication or access control.**

Anyone who can reach the UI URL can:
- Trigger pipeline runs
- View run logs (which may contain sensitive data)
- Edit Variables and Blocks (including secrets)
- Delete deployments

In `docker-local` mode this is acceptable — the UI is only reachable on your own machine (`localhost`).

In `cloud` mode, **do not share the URL with people outside the team** and ensure the server is not publicly accessible (e.g. restrict access at the firewall/security group level to known IPs only).
