# Enterprise AI Document Intelligence Platform

An internal knowledge assistant. Employees ask questions in natural language about company documents and get answers grounded in those documents, with citations to the source file, page and section. When the documents do not answer, the system says so instead of guessing.

> **Status:** work in progress. The current phase and the plan are in [ROADMAP.md](ROADMAP.md).

## How it works

```text
Upload PDF ─► Docling ─► HybridChunker ─► EmbeddingGemma ─► PostgreSQL + pgvector
Question ─► retrieve closest chunks ─► Gemini ─► grounded answer + citations (or "not found")
```

Citations are built by code from the stored chunks; the model only says which numbered sources it used, so it cannot invent a page number. Ingestion starts by itself: an Airflow DAG picks up new documents and tracks their status. Details: [ARCHITECTURE.md](ARCHITECTURE.md). Why each choice was made: [DECISIONS.md](DECISIONS.md).

## Tech stack

| Area | Technology |
|---|---|
| Language / API | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector, SQLAlchemy, Alembic |
| Object storage | MinIO locally, S3 on AWS (boto3) |
| Document processing | Docling, HybridChunker (CPU-only PyTorch) |
| AI | EmbeddingGemma (local embeddings), Gemini API (generation), RAG |
| Orchestration | Apache Airflow 3 (LocalExecutor, Docker Compose) |
| UI | Streamlit (a client of the API over HTTP) |
| Tooling | uv, Ruff, pytest, pre-commit, GitHub Actions |
| Planned | Docker image for the app, AWS (EC2, RDS, S3), Terraform |

## Getting started

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, a free Hugging Face account (EmbeddingGemma is gated) and a Gemini API key (for `/ask`). For Airflow: Docker with at least 8 GB of memory.

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

Interactive docs: http://127.0.0.1:8000/docs. Health: `/health` and `/health/db`. MinIO console: http://localhost:9001.

**Hugging Face (once per machine).** Open https://huggingface.co/google/embeddinggemma-300m while logged in, accept the license, then:

```powershell
uv run hf auth login
```

The token is saved under `HF_HOME`, outside the repository. Never commit it.

**Gemini key.** Create one in Google AI Studio (https://aistudio.google.com/apikey), put it in your local `.env` as `GEMINI_API_KEY=...` (never in `.env.example` or Git). `GEMINI_MODEL` is optional. Check the connection with two real calls on a fictional café:

```powershell
uv run python -m scripts.smoke_gemini
```

**Privacy.** On the free tier Google may use prompts and responses to improve its products. Send only fictional, openly licensed or non-sensitive documents through `/ask` (and upload only such documents in the UI); only `/ask` calls Gemini. Limits and the current model: [DECISIONS.md](DECISIONS.md) (D-28, D-36), `docs/provider_limits.md`.

**Caches (recommended on Windows).** To keep large downloads off C:, set these once and open a new terminal:

```powershell
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\path\to\_caches\uv", "User")
```

```powershell
[Environment]::SetEnvironmentVariable("HF_HOME", "D:\path\to\_caches\huggingface", "User")
```

### Airflow (automatic ingestion)

Ingestion starts by itself through Apache Airflow, which has its own Docker Compose in `airflow/`. Setup, start, stop and troubleshooting: [airflow/README.md](airflow/README.md). Start the root stack first (`docker compose up -d`): Airflow reads PostgreSQL and MinIO on your computer.

### Streamlit UI

With the API running (step 5 above), start the UI in a second terminal, from the project root:

```powershell
uv run --group ui streamlit run ui/app.py
```

Streamlit asks for an email address the first time: press Enter to skip. The page opens at http://localhost:8501 and has three parts: upload a PDF; the document list with its status, which refreshes by itself while a document waits or is processed; and a question box that shows the answer with its sources. If the API runs somewhere else, set the environment variable `API_URL` (default `http://localhost:8000`).

## Usage

The UI covers upload, status and questions. The API calls below do the same by hand.

### 1. Upload a PDF

A fictional test corpus of 14 company policy PDFs is in `data/corpus/` (origin: `data/corpus/SOURCES.md`). In `/docs` use `POST /api/v1/documents` ("Try it out"), or:

```powershell
curl.exe -F "file=@C:\path\to\your.pdf;type=application/pdf" http://localhost:8000/api/v1/documents
```

The response has the document `id` and its `status` (`uploaded`). `GET /api/v1/documents/<id>` returns its current status. Non-PDF, empty and over-`MAX_UPLOAD_MB` (default 20) files are rejected.

`GET /api/v1/documents` lists documents, newest first, as `{items, total, limit, offset}` (`limit` 1 to 100, default 20; `offset` from 0):

```powershell
curl.exe "http://localhost:8000/api/v1/documents?limit=5&offset=0"
```

### 2. Ingestion

With Airflow running and the DAG unpaused, nothing more is needed. Within about a minute the status moves on:

| Status | Meaning |
|---|---|
| `uploaded` | stored, waiting for the next DAG run |
| `processing` | claimed, being converted, embedded and stored |
| `processed` | chunks are stored, the document can answer questions |
| `failed` | ingestion raised an error; not tried again by itself |

The reason for a failure is in the Airflow UI: DAG `ingest_documents`, the red run, task `ingest`, its log. To retry a failed document, set its status back to `uploaded` (copy the `id`, do not type it):

```powershell
docker exec enterprise-doc-intelligence-postgres psql -U app -d enterprise_docs -c "update documents set status = 'uploaded' where id = '<document_id>'"
```

**Without Airflow, by hand** (pause the DAG first if it runs). It reads the PDF from MinIO, processes it, stores the chunks and sets the status; nothing goes to Gemini. A short PDF takes a few minutes on a CPU:

```powershell
uv run python -m scripts.ingest_document <document_id>
```

To upload and ingest a whole folder (the 14 corpus files take about half an hour), look first, then run. Already ingested documents are skipped, so it is safe to repeat:

```powershell
uv run python -m scripts.ingest_folder data/corpus
```

```powershell
uv run python -m scripts.ingest_folder data/corpus --run
```

### 3. Ask a question

In `/docs`, `POST /api/v1/ask`:

```json
{"question": "How many vacation days do employees get per year?", "top_k": 8}
```

`top_k` is optional (1 to 20, default 8). The response has `answer` (in the language of the question), `found` (`false` when the documents do not answer, with no citations) and `citations` (each with `filename`, `page_numbers`, `heading`, `document_id`, `text`). From PowerShell:

```powershell
function Ask($q) {
  $body = @{ question = $q; top_k = 8 } | ConvertTo-Json
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
  $r = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/ask -ContentType "application/json; charset=utf-8" -Body $bytes
  "found: $($r.found)"; "answer: $($r.answer)"
  $r.citations | ForEach-Object { "  - $($_.filename) p.$($_.page_numbers -join ',') | $($_.heading)" }
}
```

```powershell
Ask "How many vacation days do employees get per year?"
```

The first question after the API starts is slow, about 35 s (the embedding model loads). PowerShell 5.1 can display accents wrongly: check an accented answer in `/docs` before suspecting the code. If Gemini is unreachable, out of quota or returns something unusable, `/ask` returns `502` with the standard error shape; the reason is in the server log.

### Inspect retrieval without Gemini

`POST /api/v1/search` returns the retrieved chunks and their similarity, best first. Use it to tell whether a bad answer came from retrieval or from generation:

```json
{"question": "Which OCR engine can be used for scanned pages?", "top_k": 3}
```

An empty or too long question (over 1000 characters) and a `top_k` outside 1 to 20 return `422` on both endpoints.

### Try the document pipeline only

Put a PDF in `data/sample_docs/` (git-ignored). The first command prints the chunks with pages and headings without storing anything; the second shows what Docling itself produces (saved in `data/sample_docs/output/`):

```powershell
uv run python -m scripts.run_pipeline "data/sample_docs/your.pdf"
```

```powershell
uv run python scripts/explore_docling.py "data/sample_docs/your.pdf"
```

## Evaluate

A 52-question evaluation set for the corpus (`data/eval/questions.json`) and a runner. PostgreSQL must be running and the corpus ingested. Results go to `data/eval/runs/` (git-ignored); a full run also writes a `.review.md` for hand review. Kept results: [DECISIONS.md](DECISIONS.md) (E-4). A full run uses about 52 of the 500 free Gemini requests of a day.

```powershell
uv run python -m scripts.evaluate --retrieval-only
```

```powershell
uv run python -m scripts.evaluate --label mytest
```

```powershell
uv run python -m scripts.evaluate --only q07 --top-k 5
```

## Development

Run before every push (the pre-push hook runs it too): Ruff, format check and all tests.

```powershell
.\scripts\check.ps1
```

Unit tests use fakes: no Docling or embedding model, no database, and they never call Gemini. Integration tests (`tests/integration/`) use the real PostgreSQL and MinIO containers and skip themselves when unavailable. Test file names must be unique across `tests/`. CI has no Airflow: the DAG itself is checked in the container with `airflow dags list-import-errors`. The UI's API client has unit tests; the Streamlit screens are checked by hand.

## Known limitations

* Text and tables inside images are unreliable; a table can lose its header row or split across chunks. Some headings are wrong or missing, so the page number is the most reliable part of a citation.
* No similarity threshold: the model decides when to answer "not found" and a code check rejects answers without a valid citation. On the evaluation set it refused every question the documents cannot answer.
* An answer can be correct but incomplete: in the hand review of the baseline, 10 of 47 answers missed a required detail (E-4).
* No delete endpoint for documents.
* Ingestion starts up to a minute after upload, and only while Airflow runs. A `failed` document shows only its status; the reason is in the Airflow log.
* The UI's file picker shows Streamlit's default 200 MB limit; the API refuses files over 20 MB with a clear message.

Evaluation results and open items: [DECISIONS.md](DECISIONS.md) (E-4, E-5) and the backlog in [ROADMAP.md](ROADMAP.md).

## Documentation

* [PROJECT.md](PROJECT.md): product definition and V1 scope
* [ARCHITECTURE.md](ARCHITECTURE.md): how the system works today
* [DECISIONS.md](DECISIONS.md): why each choice was made
* [ROADMAP.md](ROADMAP.md): plan and progress
* [airflow/README.md](airflow/README.md): running Airflow
