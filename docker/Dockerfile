# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

# Build-time identity (filled by `make build` or `docker build --build-arg ...`)
ARG GIT_BRANCH=unknown
ARG GIT_SHA=unknown

# Surface them at runtime so they show up in worker logs and Prefect Variables
ENV GIT_BRANCH=${GIT_BRANCH} \
    GIT_SHA=${GIT_SHA} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# OS deps (curl is used by compose healthchecks; build-essential covers wheels
# that don't ship a manylinux build for python:3.11-slim)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first to leverage layer cache
COPY docker/requirements-docker.txt /app/docker/requirements-docker.txt
RUN pip install --upgrade pip \
    && pip install -r /app/docker/requirements-docker.txt

# Project source
COPY . /app

# Default workdir contents
RUN mkdir -p /app/data

LABEL org.opencontainers.image.title="pangolin" \
      org.opencontainers.image.source="https://github.com/lorygaFLO/pangolin" \
      pangolin.git.branch="${GIT_BRANCH}" \
      pangolin.git.sha="${GIT_SHA}"

# Default command is overridden per-service in docker-compose.yml
CMD ["python", "docker/deploy.py"]
