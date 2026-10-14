# syntax=docker/dockerfile:1.6
# Base image pinned to an exact Python patch + Debian release (this also pins
# the bundled pip). Bump it deliberately, never via a floating tag.
FROM python:3.11.17-slim-trixie AS base

# pangolin isn't on PyPI yet, so by default we install straight from git.
# Once it's published (PyPI or a private index), swap PANGOLIN_INSTALL_SPEC
# for a plain version pin, e.g. --build-arg PANGOLIN_INSTALL_SPEC=pangolin==0.1.0
ARG PANGOLIN_REF=main
ARG PANGOLIN_INSTALL_SPEC=git+https://github.com/lorygaFLO/pangolin.git@${PANGOLIN_REF}

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# OS deps (curl is used by compose healthchecks; build-essential covers wheels
# that don't ship a manylinux build for the pinned python base image)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the pangolin library + CLI first to leverage layer cache.
# NOTE: this layer is cached. A floating ref (PANGOLIN_REF=main) is only
# re-fetched when the layer is rebuilt — build with `--no-cache` to pick up new
# commits, or pin PANGOLIN_REF to a tag/commit for reproducible builds.
RUN pip install "pangolin @ ${PANGOLIN_INSTALL_SPEC}"

# Project-specific Python dependencies: whatever custom/ and pipelines/ import
# that pangolin doesn't already install. Listed in docker/requirements.txt
# (an empty file is fine). Copied on its own so this layer — often the heaviest
# one — stays cached until that file changes.
COPY docker/requirements.txt /tmp/project-requirements.txt
RUN pip install -r /tmp/project-requirements.txt \
    && rm /tmp/project-requirements.txt

# Build-time identity (filled by `make build` or `docker build --build-arg ...`),
# surfaced at runtime so it shows up in worker logs and Prefect Variables.
# Declared AFTER the dependency layers on purpose: it changes on every commit,
# and anything below it is rebuilt each time.
ARG GIT_BRANCH=unknown
ARG GIT_SHA=unknown
ENV GIT_BRANCH=${GIT_BRANCH} \
    GIT_SHA=${GIT_SHA}

# Project source: config/, pipelines/, custom/ (this repo, NOT the pangolin
# library — that came from PANGOLIN_INSTALL_SPEC above)
COPY . /app

# Default workdir contents
RUN mkdir -p /app/data

LABEL org.opencontainers.image.title="pangolin-project" \
      pangolin.git.branch="${GIT_BRANCH}" \
      pangolin.git.sha="${GIT_SHA}"

# Default command is overridden per-service in docker-compose.yml
CMD ["pangolin", "deploy"]
