# syntax=docker/dockerfile:1

# ---- build stage: install dependencies, then bake the embedding model ----
FROM python:3.12-slim AS builder
RUN pip install --no-cache-dir "uv>=0.12,<0.13"
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/hf-cache
ARG EMBEDDING_MODEL_ID=google/embeddinggemma-300m
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# The model is gated: the token is a build secret, never stored in a layer.
# This layer is cached, so code changes do not download it again.
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN="$(cat /run/secrets/hf_token)" \
    /opt/venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('${EMBEDDING_MODEL_ID}')"

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-cache

# ---- runtime stage ----
FROM python:3.12-slim
# OpenCV (pulled in by Docling) needs these system libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 libx11-6 libxext6 libsm6 libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
COPY --from=builder --chown=10001 /hf-cache /hf-cache
# PostgreSQL client library needed by psycopg (the Python wheel does not carry it on Linux).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/hf-cache \
    HF_HUB_OFFLINE=1
# Fail the build, not the container, if a needed package is missing.
# Runs here because the OpenCV system libraries are installed in this stage.
RUN python -c "import cv2, torch, docling, sentence_transformers, alembic, uvicorn, psycopg; psycopg.pq.version()"
WORKDIR /app
USER appuser
EXPOSE 8000
# Python's urllib: the slim image has no curl.
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/model', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
