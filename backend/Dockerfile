FROM docker.io/library/python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/venv/bin:${PATH}" \
    UV_PROJECT_ENVIRONMENT="/venv" \
    UV_LINK_MODE=copy

WORKDIR /zheka

RUN apt-get update && \
    apt-get install -y --no-install-recommends locales && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

RUN sed -i 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen ru_RU.UTF-8

ENV LANG="ru_RU.UTF-8" \
    LC_ALL="ru_RU.UTF-8" \
    TZ="Europe/Moscow"


FROM base AS build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libc6-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /uvx /usr/local/bin/

COPY ./pyproject.toml ./uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
    --frozen \
    --no-install-project \
    --no-default-groups \
    --group=fast

RUN /venv/bin/python -O -m compileall -q /venv/lib/python3.12/site-packages


FROM base AS runtime

COPY --from=build /venv /venv

COPY ./alembic.ini ./alembic.ini
COPY ./gunicorn.conf.py ./gunicorn.conf.py
COPY ./migrations ./migrations
COPY ./zheka ./zheka

RUN python -O -m compileall -q ./zheka ./migrations

ARG BUILD_COMMIT=dev
ENV BUILD_COMMIT=$BUILD_COMMIT
