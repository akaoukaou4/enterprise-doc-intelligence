# Airflow: ingestion

Airflow runs the document ingestion. It only schedules and runs; the ingestion and status logic live in `app/` ([D-45](../DECISIONS.md)). Airflow starts with the rest of the system from the root `docker-compose.yml` (see the main [README](../README.md)); there is no separate Airflow stack any more.

## What runs

| Service | Role |
|---|---|
| `airflow-db` | Airflow's own metadata database (a separate PostgreSQL, so a reset never touches documents) |
| `airflow-init` | runs once: migrates the metadata database and creates the login |
| `airflow-apiserver` | web UI and API, http://localhost:8080 (login `airflow` / `airflow`, local use only) |
| `airflow-scheduler` | runs the DAG and the ingestion tasks (LocalExecutor, no workers) |
| `airflow-dag-processor` | reads the DAG files |

All of them use one image, `enterprise-doc-airflow:3.3.2`, built from `airflow/Dockerfile`. It contains:

- Airflow 3.3.2 on its own Python, with its own pinned packages;
- the application in a **separate virtual environment** (`/opt/app-venv`, Python 3.12, built from `uv.lock`), so the app's dependencies and Airflow's never mix;
- the application code (`app/`, `scripts/`) and the DAG (`dags/`), **baked in**, no mounted folders;
- the Docling models and EmbeddingGemma, downloaded at build time. The gated embedding model needs `HF_TOKEN` from the root `.env` as a BuildKit secret during the build; the token is not stored in the image.

The containers reach PostgreSQL and MinIO by service name (`postgres:5432`, `minio:9000`), set in the root compose. Ingestion never calls Gemini, so the Airflow containers have no Gemini key.

## The DAG `ingest_documents`

Created unpaused (`DAGS_ARE_PAUSED_AT_CREATION=false` in the compose), so ingestion starts by itself. It runs every minute, one run at a time (`max_active_runs=1`, `catchup=False`):

1. `claim` runs `scripts.claim_documents --limit 5`: resets documents left in `processing` by a crash, claims up to 5 `uploaded` documents, prints their ids as JSON on the last line.
2. `build_commands` turns the ids into commands (`dags/ingest_helpers.py`, no Airflow imports, unit-tested in CI).
3. `ingest` is one mapped task per document, one at a time (`max_active_tis_per_dag=1`), one retry after 1 minute, a 45-minute timeout. Each task runs `scripts.ingest_document <id>` in the app environment.

With nothing to claim, the run ends green in a few seconds. A failed document turns its run red and its status becomes `failed`; the reason is in the task log. Status lifecycle: ARCHITECTURE section 6.2.

## Everyday commands

Run them from the project root.

See the services and their health:

```powershell
docker compose ps
```

Scheduler log (where the ingestion output goes):

```powershell
docker compose logs airflow-scheduler --tail 50
```

Check the DAG has no import errors (expected: "No data found"):

```powershell
docker compose exec airflow-scheduler airflow dags list-import-errors
```

The task log of a failed document is in the UI: http://localhost:8080, DAG `ingest_documents`, the red run, task `ingest`, Logs.

To retry a failed document, set its status back to `uploaded` (command in the main README). To pause ingestion, use the toggle in the UI; documents wait as `uploaded`. If Airflow is stopped, uploads still work and wait the same way.

## Changing things

The code and the DAG are inside the image, so after a change in `app/`, `scripts/`, `airflow/dags/`, `pyproject.toml` or `uv.lock`, rebuild and recreate:

```powershell
docker compose up -d --build
```

The slow layers (dependencies and models) come before the code layers, so a code-only change rebuilds in a minute or two. A change of `pyproject.toml` or `uv.lock` rebuilds the dependencies, which is long on a hard disk.

To upgrade Airflow, change the tag in `airflow/Dockerfile`, then compare our compose services with the official `docker-compose.yaml` of that version from the Airflow documentation (we no longer keep a copy of it).

## Limits

- **Memory.** One ingestion peaks at about 5 GiB in the scheduler container ([E-6](../DECISIONS.md)). The DAG ingests one document at a time for this reason.
- **Size.** The image is about 9.4 GB because it carries the Docling and embedding models, and the API image carries the embedding model too.
- **Offline.** `HF_HUB_OFFLINE=1` is set, so Hugging Face is not contacted. Whether ingestion runs with no internet at all (the OCR models) was not tested.
- **Retries.** A document that kills the worker is reset and retried at every run; there is no attempt counter. The reset assumes no manual ingestion runs at the same moment.
- **Security.** The Airflow login is the default and the port is published. This is for local use; Phase 12 decides access.
- A cold first start of a task can take about a minute before the work begins (E-5); the cause is not proven.
