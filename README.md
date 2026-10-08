# Enterprise AI Document Intelligence Platform

An AI-powered internal knowledge assistant. Employees ask natural-language questions about company documents and receive answers grounded in those documents, with citations to the source document and page.

> **Status:** work in progress. Phase 4 (embeddings) is complete: a PDF can be processed into chunks, embedded with EmbeddingGemma, and stored with its page numbers and headings in PostgreSQL + pgvector. Phase 5 (retrieval) is next. See [ROADMAP.md](ROADMAP.md).

## Planned workflow

```text
Upload PDF → process → chunk → embed → store in PostgreSQL + pgvector
Question → retrieve relevant chunks → Gemini → grounded answer + citations
```

## Tech stack

| Area | Technology |
|---|---|
| Language / API | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector, SQLAlchemy, Alembic |
| Object storage | MinIO (local), S3 (AWS), accessed through boto3 |
| Document processing | Docling, HybridChunker (CPU-only PyTorch) |
| AI | EmbeddingGemma through sentence-transformers (embeddings), Gemini API (generation), RAG |
| Orchestration | Apache Airflow |
| UI | Streamlit |
| Infrastructure | Docker, Docker Compose, AWS (EC2, RDS, S3), Terraform |
| Tooling | uv, Ruff, pytest, pre-commit, GitHub Actions |

Only Phases 0 to 4 are implemented so far. The rest of the stack arrives phase by phase.

## Current state

Implemented:

* FastAPI app factory, typed configuration (`pydantic-settings`), centralized logging
* unified JSON error handling
* versioned API (`/api/v1`) with a route → service pattern
* SQLAlchemy engine and session dependency, Alembic migrations (`documents` and `document_chunks` tables, pgvector extension)
* storage service (boto3): MinIO locally, the same code targets Amazon S3 on AWS
* `POST /api/v1/documents`: validates a PDF (content type, `%PDF-` bytes, size limit), stores it in MinIO, records it in PostgreSQL
* `GET /api/v1/documents/{id}`: returns the document metadata
* `/health` and `/health/db` endpoints
* document processing pipeline (`app/pipeline/`): PDF → Docling → HybridChunker → cleaning → `Chunk(text, page_numbers, heading)`. Chunk size is measured with the EmbeddingGemma tokenizer (512 tokens). It drops the table of contents, removes license watermarks and invisible characters, and does not depend on FastAPI, Airflow or the database
* `EmbeddingService`: EmbeddingGemma on CPU, 768-dimensional normalized vectors. Chunks are embedded as `title: <heading> | text: <chunk>`, questions with the model's query prompt
* `ChunkService`: stores a document's chunks, page numbers, headings and vectors in `document_chunks`, replacing the old chunks in one transaction
* `scripts/ingest_document.py`: runs the whole chain for an uploaded document (MinIO → pipeline → embeddings → PostgreSQL)
* unit tests (fakes) and integration tests (real PostgreSQL and MinIO), Ruff, pre-commit hooks, and GitHub Actions CI

Not connected yet: the upload endpoint does not start the ingestion (that arrives with Airflow in Phase 8), and there is no retrieval, Gemini or question endpoint yet (Phases 5 and 6).

## Getting started

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, and a free Hugging Face account (for EmbeddingGemma).

```powershell
# 1. Install dependencies (this installs Docling and CPU-only PyTorch, several GB)
uv sync

# 2. Create your environment file and fill in the values
copy .env.example .env

# 3. Start PostgreSQL and MinIO (this also creates the "documents" bucket)
docker compose up -d

# 4. Create the database tables (also enables the pgvector extension)
uv run alembic upgrade head

# 5. Run the API
uv run uvicorn app.main:app --reload
```

Once the server is running:

* Interactive docs: http://127.0.0.1:8000/docs
* Health: http://127.0.0.1:8000/health
* Database health: http://127.0.0.1:8000/health/db
* Info: http://127.0.0.1:8000/api/v1/info
* MinIO console: http://localhost:9001

### Hugging Face access (needed for EmbeddingGemma)

EmbeddingGemma is a gated model. Once per machine:

1. Open https://huggingface.co/google/embeddinggemma-300m while logged in and accept the license.
2. Log in from the project:

```powershell
uv run hf auth login
uv run hf auth whoami
```

The token is saved under `HF_HOME`, outside the repository. Never put it in `.env.example` or commit it.

### Where the caches go (recommended on Windows)

Docling, PyTorch and EmbeddingGemma are large. By default uv and Hugging Face cache their downloads under your user folder on C:. To keep them on another drive, set these user environment variables once, then open a new terminal:

```powershell
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\path\to\_caches\uv", "User")
[Environment]::SetEnvironmentVariable("HF_HOME", "D:\path\to\_caches\huggingface", "User")
```

### Try an upload

Open the interactive docs, use `POST /api/v1/documents` ("Try it out"), and choose a PDF. Or from PowerShell:

```powershell
curl.exe -F "file=@C:\path\to\your.pdf;type=application/pdf" http://localhost:8000/api/v1/documents
```

The response contains the document `id`; `GET /api/v1/documents/<id>` returns its metadata. Files that are not PDFs, are empty, or are larger than `MAX_UPLOAD_MB` (default 20) are rejected.

### Ingest an uploaded document

This reads the PDF from MinIO, processes it, embeds the chunks and stores them in PostgreSQL. Running it again replaces the document's chunks.

```powershell
uv run python -m scripts.ingest_document <document_id>
```

On a CPU, a 9-page PDF takes about 3 to 4 minutes (about 10 s per page for Docling, plus about 1.6 s per chunk for embeddings). The first run also loads the models.

### Try the document pipeline only

Put a PDF in `data/sample_docs/` (PDFs there are git-ignored), then run the pipeline without storing anything:

```powershell
uv run python -m scripts.run_pipeline "data/sample_docs/your.pdf"
```

It prints the number of chunks, the pages covered, and the first chunks with their pages and headings.

To look at what Docling itself produces for a PDF (pages, headings, tables, and the saved Markdown and JSON in `data/sample_docs/output/`):

```powershell
uv run python scripts/explore_docling.py "data/sample_docs/your.pdf"
```

## Development

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Integration tests (`tests/integration/`) use the real PostgreSQL and MinIO containers. They skip themselves automatically when those services are not available, so `uv run pytest` also works without Docker running. The pipeline and embedding unit tests use fakes and need no Docling or EmbeddingGemma models.

## Known limitations

Document processing (Phase 3):

* Text and tables inside embedded images are unreliable.
* Docling reports every heading as level 1, and some headings are wrong or missing, so the page number is the most reliable part of a citation.
* A table can lose its header row or be split across chunks.

Retrieval (seen in Phase 4):

* Dense vector search always returns the nearest chunks, even when the document cannot answer the question. Deciding when to answer "not found" is handled in Phases 6 and 7.
* Bibliography chunks can be returned for questions that mention a cited tool.

These are recorded in [DECISIONS.md](DECISIONS.md) and will be measured in the Phase 7 evaluation before any fix is attempted.

## Documentation

* [PROJECT.md](PROJECT.md) - product definition and V1 scope
* [ARCHITECTURE.md](ARCHITECTURE.md) - system architecture
* [ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md) - engineering rules
* [DECISIONS.md](DECISIONS.md) - technical decisions and their reasoning
* [ROADMAP.md](ROADMAP.md) - development plan and progress
