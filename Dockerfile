# https://github.com/astral-sh/uv/issues/7758#issuecomment-3263282018
FROM cgr.dev/chainguard/wolfi-base AS base
FROM base AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PYTHON_CACHE_DIR=/root/.cache/uv/python \
    UV_PYTHON=3.11.14
WORKDIR /app

COPY --link src/ src/
COPY --link LICENSE pyproject.toml README.md uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM base
COPY --from=build --chown=nonroot:nonroot --chmod=755 /opt/python /opt/python
COPY --from=build --chown=nonroot:nonroot --chmod=755 /app /app
WORKDIR /app
USER nonroot

VOLUME /home/nonroot/.local/share/ministatus

ENV PATH=/app/.venv/bin:${PATH} \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1
STOPSIGNAL SIGINT
ENTRYPOINT ["ministatus"]
