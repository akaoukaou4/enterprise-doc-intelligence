# syntax=docker/dockerfile:1
FROM apache/airflow:3.3.2

# OpenCV (used by Docling) needs these system libraries.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 libx11-6 libxext6 libsm6 libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /opt/app /opt/app-venv /opt/uv-python /opt/hf-cache \
    && chown -R airflow:0 /opt/app /opt/app-venv /opt/uv-python /opt/hf-cache
USER airflow

# The app gets its own venv, separate from Airflow's pinned packages.
RUN pip install --no-cache-dir "uv>=0.12,<0.13"
ENV UV_PROJECT_ENVIRONMENT=/opt/app-venv \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    HF_HOME=/opt/hf-cache

WORKDIR /opt/app
COPY --chown=airflow:0 pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --python 3.12 --no-cache
# Fail the build, not the task, if the app venv cannot import its heavy dependencies.
RUN /opt/app-venv/bin/python -c "import cv2, torch, docling"

# Bake the models. These two layers come before the code, so a code change does not download them again.
# 1) Docling: starting its PDF pipeline downloads layout, table and OCR models.
RUN /opt/app-venv/bin/python -c "from docling.datamodel.base_models import InputFormat; from docling.document_converter import DocumentConverter; DocumentConverter().initialize_pipeline(InputFormat.PDF)"
# 2) EmbeddingGemma (gated): the token is a build secret, never stored in a layer.
ARG EMBEDDING_MODEL_ID=google/embeddinggemma-300m
RUN --mount=type=secret,id=hf_token,uid=50000 \
    HF_TOKEN="$(cat /run/secrets/hf_token)" \
    /opt/app-venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('${EMBEDDING_MODEL_ID}')"
ENV HF_HUB_OFFLINE=1

# The code and the DAG are inside the image (no mounts).
COPY --chown=airflow:0 app ./app
COPY --chown=airflow:0 scripts ./scripts
COPY --chown=airflow:0 airflow/dags /opt/airflow/dags

WORKDIR /opt/airflow
