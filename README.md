# Enterprise AI Document Intelligence Platform

An AI-powered internal knowledge assistant. Employees ask natural-language questions about company documents and receive answers grounded in those documents, with citations to the source document and page.

> **Status:** work in progress. Phase 1 (FastAPI foundation) is complete. Phase 2 (database and object storage) is next. See [ROADMAP.md](ROADMAP.md).

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
| Object storage | MinIO (local), S3 (AWS) |
| Document processing | Docling, HybridChunker |
| AI | EmbeddingGemma (embeddings), Gemini API (generation), RAG |
| Orchestration | Apache Airflow |
| UI | Streamlit |
| Infrastructure | Docker, Docker Compose, AWS (EC2, RDS, S3), Terraform |
| Tooling | uv, Ruff, pytest, pre-commit, GitHub Actions |

Only Phases 0 and 1 are implemented so far. The rest of the stack arrives phase by phase.

## Current state

Implemented:

* FastAPI app factory, typed configuration (`pydantic-settings`), centralized logging
* unified JSON error handling
* versioned API (`/api/v1`) with a route → service pattern
* SQLAlchemy engine and session dependency
* `/health` and `/health/db` endpoints
* unit tests, Ruff, pre-commit hooks, and GitHub Actions CI

## Getting started

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), Docker.

```powershell
# 1. Install dependencies
uv sync

# 2. Create your environment file and fill in the values
copy .env.example .env

# 3. Start PostgreSQL and MinIO
docker compose up -d

# 4. Run the API
uv run uvicorn app.main:app --reload
```

Once the server is running:

* Interactive docs: http://127.0.0.1:8000/docs
* Health: http://127.0.0.1:8000/health
* Database health: http://127.0.0.1:8000/health/db
* Info: http://127.0.0.1:8000/api/v1/info

## Development

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Documentation

* [PROJECT.md](PROJECT.md) - product definition and V1 scope
* [ARCHITECTURE.md](ARCHITECTURE.md) - system architecture
* [ENGINEERING_PRINCIPLES.md](ENGINEERING_PRINCIPLES.md) - engineering rules
* [DECISIONS.md](DECISIONS.md) - technical decisions and their reasoning
* [ROADMAP.md](ROADMAP.md) - development plan and progress
