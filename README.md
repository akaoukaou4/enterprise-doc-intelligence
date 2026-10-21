# Enterprise AI Document Intelligence Platform

An internal knowledge assistant. Employees ask questions in natural language about company documents and get answers grounded in those documents, with citations to the source file, page and section. When the documents do not answer, the system says so instead of guessing.

> **Status:** work in progress. The current phase and the plan are in [ROADMAP.md](ROADMAP.md).

## How it works

```text
Upload PDF ─► Docling ─► HybridChunker ─► EmbeddingGemma ─► PostgreSQL + pgvector
Question ─► retrieve closest chunks ─► Gemini ─► grounded answer + citations (or "not found")
```

Citations are built by code from the stored chunks. The model only says which numbered sources it used, so it cannot invent a page number. Ingestion (everything after the upload) starts by itself: an Airflow DAG picks up new documents and tracks their status. Details: [ARCHITECTURE.md](ARCHITECTURE.md).

## Tech stack

| Area | Technology |
|---|---|
| Language / API | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector, SQLAlchemy, Alembic |
| Object storage | MinIO locally, S3 on AWS (through boto3) |
| Document processing | Docling, HybridChunker (CPU-only PyTorch) |
| AI | EmbeddingGemma (embeddings, local), Gemini API (generation), RAG |
| Orchestration | Apache Airflow 3 (LocalExecutor, Docker Compose) |
| Tooling | uv, Ruff, pytest, pre-commit, GitHub Actions |
| Planned | Streamlit, Docker image for the app, AWS (EC2, RDS, S3), Terraform |

Why each choice was made: [DECISIONS.md](DECISIONS.md).

## Getting started

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, a free Hugging Face account (for EmbeddingGemma) and a Gemini API key (for `/ask`). For Airflow: Docker with at least 8 GB of memory (one ingestion peaks at about 5 GB).

```powershell
# 1. Install dependencies (Docling and CPU-only PyTorch: several GB)
uv sync

# 2. Create your environment file and fill in the values (including GEMINI_API_KEY)
copy .env.example .env

# 3. Start PostgreSQL and MinIO (also creates the "documents" bucket)
docker compose up -d

# 4. Create the database tables (also enables the pgvector extension)
uv run alembic upgrade head

# 5. Run the API
uv run uvicorn app.main:app --reload
```

Links once the server runs:

* Interactive docs: http://127.0.0.1:8000/docs
* Health: http://127.0.0.1:8000/health and http://127.0.0.1:8000/health/db
* MinIO console: http://localhost:9001

### Hugging Face access (EmbeddingGemma is gated)

Once per machine: open https://huggingface.co/google/embeddinggemma-300m while logged in and accept the license, then:

```powershell
uv run hf auth login
uv run hf auth whoami
```

The token is saved under `HF_HOME`, outside the repository. Never put it in `.env.example` or commit it.

### Gemini API key

1. Create a key in Google AI Studio: https://aistudio.google.com/apikey
2. Put it in your local `.env` (never in `.env.example`, never in Git): `GEMINI_API_KEY=your-key-here`
3. Optional: choose another model with `GEMINI_MODEL`.
4. Check the connection (two real calls, using a fictional café as the document): `uv run python -m scripts.smoke_gemini`

**Privacy:** on the free tier, Google may use prompts and responses to improve its products. Send only fictional, openly licensed or non-sensitive documents through `/ask`. Quotas and the current default model: [DECISIONS.md](DECISIONS.md) (D-28, D-36) and `docs/provider_limits.md`. Only `/ask` calls Gemini; upload, ingestion and `/search` do not.

### Where the caches go (recommended on Windows)

uv and Hugging Face cache large downloads under your user folder on C: by default. To keep them elsewhere, set these once and open a new terminal:

```powershell
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\path\to\_caches\uv", "User")
[Environment]::SetEnvironmentVariable("HF_HOME", "D:\path\to\_caches\huggingface", "User")
```

### Airflow (automatic ingestion)

Airflow has its own Docker Compose in `airflow/`. The root `docker compose up -d` does not start it, so API work stays light. Start the root stack first: Airflow reads PostgreSQL and MinIO on your computer.

**First time only.** Create the file `airflow\.env` (it is git-ignored; never commit it):

| Key | Value |
|---|---|
| `AIRFLOW_UID` | `50000` |
| `FERNET_KEY` | a new random key, see the command below |
| `DATABASE_URL` | the value from the root `.env`, with `host.docker.internal` instead of `localhost` or `127.0.0.1` |
| `MINIO_ENDPOINT` | `http://host.docker.internal:9000` |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | the same as the root `.env` |
| `HF_TOKEN` | your Hugging Face token (the model is gated) |

Do not copy `GEMINI_API_KEY`: ingestion never calls Gemini. A Fernet key is 32 random bytes in URL-safe base64; this prints one:

```powershell
$b = New-Object byte[] 32; (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($b); [Convert]::ToBase64String($b).Replace('+','-').Replace('/','_')
```

Then build and initialize (a few GB and several minutes the first time):

```powershell
cd airflow
docker compose build
docker compose up airflow-init
docker compose up -d
```

The UI is at http://localhost:8080 (login `airflow` / `airflow`, local use only). The DAG `ingest_documents` is created paused. Unpause it once, from the `airflow` folder:

```powershell
docker compose exec airflow-scheduler airflow dags unpause ingest_documents
docker compose exec airflow-scheduler airflow dags list-import-errors
```

The second command must print "No data found" (no import errors). **Pause the DAG when you stop working** (it polls every minute), then stop the stack:

```powershell
docker compose exec airflow-scheduler airflow dags pause ingest_documents
docker compose down
```

Never run `docker compose down -v` unless you mean it: it deletes the `hf-cache` volume (a download of about 12 minutes) and the Airflow history.

**Timing.** The first ingestion in a new container also downloads the models (17.5 minutes measured). After that a short PDF takes about 4 minutes from upload to `processed`. One ingestion runs at a time. If you change `pyproject.toml` or `uv.lock`, run `docker compose build` again; a change in `app/` or `scripts/` needs no rebuild (they are mounted).

## Usage

### 1. Upload a PDF

A fictional test corpus of company policy PDFs is in `data/corpus/` (origin: `data/corpus/SOURCES.md`). Use it to try the system. In `/docs`, use `POST /api/v1/documents` ("Try it out"), or:

```powershell
curl.exe -F "file=@C:\path\to\your.pdf;type=application/pdf" http://localhost:8000/api/v1/documents
```

The response contains the document `id` and its `status` (`uploaded`). `GET /api/v1/documents/<id>` returns its metadata and current status. Files that are not PDFs, are empty, or exceed `MAX_UPLOAD_MB` (default 20) are rejected.

### 2. Ingestion

With Airflow running and the DAG unpaused, nothing more is needed. Within about a minute the document becomes `processing`, then `processed` (ready for questions) or `failed`:

| Status | Meaning |
|---|---|
| `uploaded` | stored, waiting for the next DAG run |
| `processing` | claimed, being converted, embedded and stored |
| `processed` | chunks are stored, the document can answer questions |
| `failed` | ingestion raised an error; it is not tried again by itself |

The reason for a failure is in the Airflow UI: open the DAG `ingest_documents`, the run (red), the task `ingest`, then its log. To try a failed document again, set its status back to `uploaded` (copy the `id`, do not type it):

```powershell
docker exec enterprise-doc-intelligence-postgres psql -U app -d enterprise_docs -c "update documents set status = 'uploaded' where id = '<document_id>'"
```

**Without Airflow, by hand.** Pause the DAG first if it is running, then:

```powershell
uv run python -m scripts.ingest_document <document_id>
```

It reads the PDF from MinIO, processes it, embeds the chunks, stores them and sets the status. Running it again replaces the document's chunks. Nothing is sent to Gemini. On a CPU a short PDF takes a few minutes, and the first run also loads the models.

To upload and ingest a whole folder (for example the corpus), look at what it would do first, then run it. A document that is already ingested is skipped, so it is safe to repeat. The 14 corpus files take about half an hour on a CPU:

```powershell
uv run python -m scripts.ingest_folder data/corpus
uv run python -m scripts.ingest_folder data/corpus --run
```

### 3. Ask a question

In `/docs`, expand `POST /api/v1/ask` and send:

```json
{"question": "How many vacation days do employees get per year?", "top_k": 8}
```

`top_k` is optional (1 to 20, default 8).

The response:

* `answer`: the grounded answer, in the language of the question
* `found`: `true` if the documents answer it, `false` if not
* `citations`: the chunks the answer is based on, each with `filename`, `page_numbers`, `heading`, `document_id` and `text`. A `found: false` answer has no citations

From PowerShell (the question is sent as UTF-8 so accents survive):

```powershell
function Ask($q) {
  $body = @{ question = $q; top_k = 8 } | ConvertTo-Json
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
  $r = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/ask -ContentType "application/json; charset=utf-8" -Body $bytes
  "found: $($r.found)"
  "answer: $($r.answer)"
  $r.citations | ForEach-Object { "  - $($_.filename) p.$($_.page_numbers -join ',') | $($_.heading)" }
}

Ask "How many vacation days do employees get per year?"
```

The first question after the server starts is slow because the embedding model loads. Windows PowerShell 5.1 can display non-ASCII characters incorrectly: check an accented answer in `/docs` before suspecting the code. If Gemini cannot be reached, is out of quota or returns something unusable, `/ask` returns `502` with the standard error shape; the reason is in the server log.

### Inspect retrieval without Gemini

`POST /api/v1/search` returns the retrieved chunks and their similarity, best first. Use it to tell whether a bad answer came from retrieval or from generation:

```json
{"question": "Which OCR engine can be used for scanned pages?", "top_k": 3}
```

An empty or too long question (over 1000 characters) and a `top_k` outside 1 to 20 return `422` on both `/search` and `/ask`.

### Try the document pipeline only

Put a PDF in `data/sample_docs/` (git-ignored), then:

```powershell
uv run python -m scripts.run_pipeline "data/sample_docs/your.pdf"
uv run python scripts/explore_docling.py "data/sample_docs/your.pdf"
```

The first prints the chunks with their pages and headings, without storing anything. The second shows what Docling itself produces (output saved in `data/sample_docs/output/`).

## Evaluate

The repository includes a 52-question evaluation set for the corpus (`data/eval/questions.json`) and a runner. PostgreSQL must be running and the corpus ingested.

```powershell
uv run python -m scripts.evaluate --retrieval-only       # no Gemini calls, about 1 to 3 minutes
uv run python -m scripts.evaluate --label mytest          # full run, about 6 minutes (paced for the free tier)
uv run python -m scripts.evaluate --only q07 --top-k 5    # one question, another answer size
```

Results go to `data/eval/runs/` (git-ignored). A full run also writes a `.review.md` file: read the answers and fill in the verdicts. Kept results and what they mean: [DECISIONS.md](DECISIONS.md) (E-4). A full run uses about 52 of the 500 free Gemini requests of a day.

## Development

```powershell
.\scripts\check.ps1
```

This runs Ruff and the unit and integration tests, and is the one command to run before every push (the pre-push hook runs it too). Individual commands:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Unit tests use fakes: no Docling or embedding model, no database, and they never call Gemini. Integration tests (`tests/integration/`) use the real PostgreSQL and MinIO containers (`docker compose up -d` first) and skip themselves when those are not available. Test file names must be unique across `tests/` (no `__init__.py`, so a duplicate name stops pytest at collection). CI has no Airflow: the DAG itself is checked inside the container with `airflow dags list-import-errors` (see "Airflow").

## Known limitations

* Text and tables inside embedded images are unreliable; a table can lose its header row or split across chunks.
* Some section headings are wrong or missing, so the page number is the most reliable part of a citation.
* There is no similarity threshold: the model decides when to answer "not found", and a code check rejects answers without a valid citation. On the evaluation set it refused every question the documents cannot answer.
* An answer can be correct but incomplete: in the hand review of the baseline, 10 of 47 answers missed a required detail (DECISIONS, E-4).
* No list or delete endpoint for documents.
* Ingestion starts up to a minute after upload, and only while Airflow runs. A `failed` document shows only its status; the reason is in the Airflow log.

Evaluation results and open items: [DECISIONS.md](DECISIONS.md) (E-4, E-5) and the backlog in [ROADMAP.md](ROADMAP.md).

## Documentation

* [PROJECT.md](PROJECT.md): product definition and V1 scope
* [ARCHITECTURE.md](ARCHITECTURE.md): how the system works today
* [DECISIONS.md](DECISIONS.md): why each choice was made
* [ROADMAP.md](ROADMAP.md): plan and progress
