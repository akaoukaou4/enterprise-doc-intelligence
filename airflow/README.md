# Airflow: automatic ingestion

Airflow runs the DAG `ingest_documents`: every minute it claims new `uploaded` documents and ingests them one at a time (why: DECISIONS D-43 to D-46). This folder has its own Docker Compose. The root `docker compose up -d` does not start it. Requirement: Docker with at least 8 GB of memory.

All commands below run from this folder (`cd airflow`). Start the root stack first: Airflow reads PostgreSQL and MinIO on your computer.

## First time only

Create `airflow\.env` (git-ignored, never commit it):

| Key | Value |
|---|---|
| `AIRFLOW_UID` | `50000` |
| `FERNET_KEY` | a new random key (command below) |
| `DATABASE_URL` | the root `.env` value, with `host.docker.internal` instead of `localhost` or `127.0.0.1` |
| `MINIO_ENDPOINT` | `http://host.docker.internal:9000` |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | the same as the root `.env` |
| `HF_TOKEN` | your Hugging Face token |

Do not copy `GEMINI_API_KEY`: ingestion never calls Gemini. A Fernet key is 32 random bytes in URL-safe base64; this prints one:

```powershell
$b = New-Object byte[] 32; (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($b); [Convert]::ToBase64String($b).Replace('+','-').Replace('/','_')
```

Build and initialize (a few GB and several minutes the first time):

```powershell
docker compose build
```

```powershell
docker compose up airflow-init
```

```powershell
docker compose up -d
```

The UI is at http://localhost:8080 (login `airflow` / `airflow`, local use only). The DAG starts paused. Unpause it once, then check it has no import errors (the second command must print "No data found"):

```powershell
docker compose exec airflow-scheduler airflow dags unpause ingest_documents
```

```powershell
docker compose exec airflow-scheduler airflow dags list-import-errors
```

## Daily use

Start: `docker compose up -d`. The DAG keeps the paused or unpaused state it had when you stopped. An unpaused DAG polls every minute as soon as the stack is up.

**When you stop working**, pause the DAG, then stop the stack:

```powershell
docker compose exec airflow-scheduler airflow dags pause ingest_documents
```

```powershell
docker compose down
```

If the first command says `service "airflow-scheduler" is not running`, the stack is already stopped and there is nothing to pause. Start it again and pause the DAG if you do not want polling.

Never run `docker compose down -v` unless you mean it: it deletes the `hf-cache` volume (a download of about 12 minutes) and the Airflow history.

## Timing and changes

- The first ingestion in a new container downloads the models (17.5 minutes measured). After that a short PDF takes about 4 minutes from upload to `processed`, one at a time (DECISIONS E-5).
- A change in `pyproject.toml` or `uv.lock` needs `docker compose build`. A change in `app/` or `scripts/` does not (they are mounted).

## When a document fails

The status is `failed`. The reason is in the Airflow UI: DAG `ingest_documents`, the red run, task `ingest`, its log. How to retry a failed document: root README, "Ingestion".
