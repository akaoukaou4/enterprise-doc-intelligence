FROM apache/airflow:3.3.2

USER root
RUN mkdir -p /opt/app /opt/app-venv /opt/uv-python /opt/hf-cache \
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

# OpenCV (used by Docling) needs these system libraries.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 libx11-6 libxext6 libsm6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*
USER airflow

# Fail the build, not the task, if the app venv cannot import its heavy dependencies.
RUN /opt/app-venv/bin/python -c "import cv2, torch, docling"

WORKDIR /opt/airflow
