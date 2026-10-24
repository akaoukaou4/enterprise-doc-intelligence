# Enterprise AI Document Intelligence Platform

An internal knowledge assistant. Employees ask questions in natural language about company documents and get answers grounded in those documents, with citations to the source file, page and section. When the documents do not answer, the system says so instead of guessing.

> **Status:** work in progress. The current phase and the plan are in [ROADMAP.md](ROADMAP.md).

## How it works

Upload PDF > Docling > HybridChunker > EmbeddingGemma > PostgreSQL + pgvector.
Question > closest chunks > Gemini > grounded answer with citations, or "not found".

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
| UI | Streamlit (an HTTP client of the API) |
| Tooling | uv, Ruff, pytest, pre-commit, GitHub Actions |
| Planned | Docker image for the app, AWS (EC2, RDS, S3), Terraform |

## Getting started

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker (8 GB of memory for Airflow), a free Hugging Face account (EmbeddingGemma is gated) and a Gemini API key (for questions).

**One-time setup**

```powershell
uv sync
```

```powershell
copy .env.example .env
```

Edit `.env`: set `GEMINI_API_KEY` (create one in [Google AI Studio](https://aistudio.google.com/apikey); never put it in `.env.example` or Git) and `PRELOAD_EMBEDDING_MODEL=true`. The template alone changes nothing: the real `.env` must be edited.

EmbeddingGemma: open https://huggingface.co/google/embeddinggemma-300m while logged in, accept the license, then run this once per machine (the token is saved outside the repository):

```powershell
uv run hf auth login
```

Optional, on Windows: keep large downloads off C: by setting `UV_CACHE_DIR` and `HF_HOME` (User environment variables) to a folder on another drive, then open a new terminal.

**Every session**, in this order, each in its own terminal, from the project root:

```powershell
docker compose up -d
```

```powershell
uv run alembic upgrade head
```

```powershell
uv run uvicorn app.main:app
```

```powershell
uv run --group ui streamlit run ui/app.py
```

Airflow has its own compose: [airflow/README.md](airflow/README.md). Unpause the DAG `ingest_documents` once; pause it when you stop working.

- UI: http://localhost:8501 (the first start asks for an email: press Enter).
- API docs: http://localhost:8000/docs. Health: `/health`, `/health/db`, `/health/model`. MinIO console: http://localhost:9001.
- If the API runs elsewhere, set `API_URL` for the UI (default `http://localhost:8000`).
- With `--reload` every code save reloads the model: add it only while editing API code, with `PRELOAD_EMBEDDING_MODEL=false`.

**Model preload.** The API loads the embedding model in the background at start (about 26 s, longer on a cold disk) and answers requests meanwhile. `GET /health/model` returns `503 loading`, then `200 ready`; the UI shows the same in its status line. A question asked before it is ready waits for the load.

**Check the Gemini connection** with two real calls on a fictional cafe:

```powershell
uv run python -m scripts.smoke_gemini
```

**Privacy.** On the free tier Google may use prompts and responses to improve its products. Send only fictional, openly licensed or non-sensitive documents through questions (and upload only such documents). Only questions call Gemini; ingestion, embeddings and search run locally. Details: [DECISIONS.md](DECISIONS.md) (D-28, D-36), `docs/provider_limits.md`.

## Usage

The UI covers upload, status and questions (the file picker allows up to 20 MB, set in `.streamlit/config.toml`). The same calls are in the API docs at `/docs`.

**Upload.** `POST /api/v1/documents` (PDF only, up to `MAX_UPLOAD_MB`, default 20). A fictional test corpus of 14 policy PDFs is in `data/corpus/` (origin: `data/corpus/SOURCES.md`).

```powershell
curl.exe -F "file=@C:\path\to\your.pdf;type=application/pdf" http://localhost:8000/api/v1/documents
```

**List and status.** `GET /api/v1/documents?limit=20&offset=0` (newest first). `GET /api/v1/documents/<id>` shows one document. With Airflow running, the status moves on within about a minute:

| Status | Meaning |
|---|---|
| `uploaded` | stored, waiting for the next DAG run |
| `processing` | claimed, being converted, embedded and stored |
| `processed` | chunks are stored, the document can answer questions |
| `failed` | ingestion raised an error; not tried again by itself |

The reason for a failure is in the Airflow UI (DAG `ingest_documents`, the red run, task `ingest`, its log). To retry a failed document, set its status back to `uploaded` (copy the id, do not type it):

```powershell
docker exec enterprise-doc-intelligence-postgres psql -U app -d enterprise_docs -c "update documents set status = 'uploaded' where id = '<document_id>'"
```

**Delete.** `DELETE /api/v1/documents/<id>` removes the document, its chunks and its file (`204`; `404` unknown id; `409` while it is `processing`). There is no authentication yet.

**Ingest without Airflow** (pause the DAG first). One stored document, or a whole folder (look first, then `--run`; already ingested files are skipped):

```powershell
uv run python -m scripts.ingest_document <document_id>
```

```powershell
uv run python -m scripts.ingest_folder data/corpus --run
```

**Ask.** `POST /api/v1/ask` with `{"question": "How many vacation days do employees get per year?", "top_k": 8}`. `top_k` is optional (1 to 20, default 8): how many chunks are retrieved and sent to Gemini. The response has `answer` (in the language of the question), `found` (`false` when the documents do not answer, with no citations) and `citations` (`filename`, `page_numbers`, `heading`, `document_id`, `text`). Accented text in PowerShell 5.1 can display wrongly: check in `/docs` before suspecting the code. If Gemini is unreachable or out of quota, the API returns `502`; the reason is in the server log.

**Inspect retrieval without Gemini.** `POST /api/v1/search` returns the retrieved chunks and their similarity, best first: it shows whether a bad answer came from retrieval or from generation.

**Pipeline only.** Put a PDF in `data/sample_docs/` (git-ignored) and print its chunks without storing anything: `uv run python -m scripts.run_pipeline "data/sample_docs/your.pdf"`.

## Check the whole system

With everything running (API, Airflow with the DAG unpaused, a Gemini key), this uploads a fictional PDF, waits for ingestion, checks search, one answer and one refusal, then deletes it. About 5 minutes and 2 Gemini requests. Set `API_URL` to test another environment.

```powershell
uv run python -m scripts.e2e_check
```

## Evaluate

A 52-question set (`data/eval/questions.json`) and a runner; PostgreSQL must be running and the corpus ingested. Results go to `data/eval/runs/` (git-ignored); a full run also writes a `.review.md` for hand review. Kept results: [DECISIONS.md](DECISIONS.md) (E-4). A full run uses about 52 of the 500 free Gemini requests of a day.

```powershell
uv run python -m scripts.evaluate --retrieval-only
```

```powershell
uv run python -m scripts.evaluate --label mytest
```

## Development

Run before every push (the pre-push hook runs it too). Start the containers first, or the integration tests skip.

```powershell
.\scripts\check.ps1
```

Unit tests use fakes: no Docling or model, no database, and they never call Gemini. Integration tests (`tests/integration/`) use the real PostgreSQL and MinIO and skip themselves when unavailable. Test file names must be unique across `tests/`. CI has no Airflow: the DAG is checked in the container with `airflow dags list-import-errors`. The Streamlit screens are checked by hand.

## Known limitations

* Text and tables inside images are unreliable; a table can lose its header row or split across chunks. Some headings are wrong or missing, so the page number is the most reliable part of a citation.
* No similarity threshold: the model decides when to answer "not found", and a code check rejects answers without a valid citation. On the evaluation set it refused every question the documents cannot answer.
* An answer can be correct but incomplete: in the hand review of the baseline, 10 of 47 answers missed a required detail (E-4).
* No authentication: anyone who can reach the API can upload and delete.
* Ingestion starts up to a minute after upload, and only while Airflow runs. A `failed` document shows only its status; the reason is in the Airflow log.

Evaluation results and open items: [DECISIONS.md](DECISIONS.md) (E-4, E-5) and the backlog in [ROADMAP.md](ROADMAP.md).

## Documentation

* [PROJECT.md](PROJECT.md): product definition and V1 scope
* [ARCHITECTURE.md](ARCHITECTURE.md): how the system works today
* [DECISIONS.md](DECISIONS.md): why each choice was made
* [ROADMAP.md](ROADMAP.md): plan and progress
* [airflow/README.md](airflow/README.md): running Airflow
