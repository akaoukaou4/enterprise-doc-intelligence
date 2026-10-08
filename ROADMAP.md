# Roadmap

## Purpose

This roadmap defines the development order for the **Enterprise AI Document Intelligence Platform**.

The roadmap is designed around one main objective:

> **Build a complete AI Engineering system as quickly as reasonably possible, while learning the underlying technologies deeply enough to understand and defend the system.**

The project should progress from a simple working core toward a production-oriented deployment.

The development order should prioritize:

1. AI Engineering
2. Data Engineering
3. Backend Engineering
4. Cloud / DevOps
5. Production quality

Advanced technologies should only be introduced after the core system works.

---

# Development Strategy

The overall progression is:

```text
Foundation
    ↓
Backend
    ↓
Data + Storage
    ↓
Document Processing
    ↓
Embeddings
    ↓
Retrieval
    ↓
RAG + Gemini
    ↓
Evaluation
    ↓
Airflow
    ↓
UI
    ↓
Docker / Production
    ↓
AWS
    ↓
Terraform
    ↓
Portfolio Polish
```

The most important milestone is:

> **A user can upload a document, ask a question, and receive a grounded answer with a source citation.**

Everything before that milestone exists to make this workflow possible.

Everything after it exists to improve, productionize, evaluate, or deploy it.

---

# Phase 0 — Project Foundation

### Status

**Complete**

### Objectives

Create a clean development environment and repository foundation.

### Completed

* Git repository
* GitHub repository
* project structure
* Python 3.12 environment
* `uv`
* `pyproject.toml`
* Ruff
* pytest
* pre-commit
* GitHub Actions CI
* Docker
* Docker Compose
* PostgreSQL
* pgvector
* MinIO
* environment configuration
* basic project documentation

### Important checkpoint

The project can be cloned and the development environment can be initialized consistently.

---

# Phase 1 — FastAPI Application Foundation

### Status

**Complete**

### Objective

Create the backend application and establish the basic application structure.

### Completed

* FastAPI application factory (`create_app()`)
* configuration management with `pydantic-settings` (`.env` and environment variables)
* centralized logging
* `/health` endpoint
* `/health/db` readiness endpoint (checks the PostgreSQL connection)
* versioned API router (`/api/v1`)
* Pydantic schemas
* service layer skeleton (route → service pattern, example `InfoService` and `/api/v1/info`)
* SQLAlchemy engine, session factory, and `get_db` dependency
* unified error handling (custom exceptions, one JSON error shape, no leaked internals)
* unit tests, Ruff, pre-commit, and green GitHub Actions CI

### Result

```text
FastAPI
   │
   ├── /health
   ├── /health/db
   ├── /api/v1/info
   └── application structure ready
        (config, logging, errors, services, DB session)
```

### Learning focus

* FastAPI
* dependency injection
* Pydantic
* application configuration
* backend structure

### Exit condition

The API starts successfully and basic tests pass.

**Met:** the API starts, `/health/db` was verified against the real PostgreSQL container (including an outage and recovery test), 13 tests pass, and CI is green.

---

# Phase 2 — Database and Object Storage

### Status

**Complete**

### Objective

Build the data foundation required by the application.

### Completed

PostgreSQL:

* storage settings in the typed `Settings` object (`MINIO_*`, `MAX_UPLOAD_MB`)
* SQLAlchemy declarative `Base` and the `Document` model
* Alembic migrations (`migrations/`), with the database URL read from `Settings`
* first migration: `documents` table (verified, including a downgrade and upgrade round trip)
* Ruff excludes the Alembic-generated `migrations/versions/` folder

Object storage:

* `StorageService` (`upload`, `download`, `delete`) using `boto3`, the only code that knows about the S3 API
* MinIO locally; the same code targets Amazon S3 when `MINIO_ENDPOINT` is not set
* boto3 failures mapped to `NotFoundError` / `ExternalServiceError`

API:

* `POST /api/v1/documents` (validates a PDF, stores the file, inserts the row)
* `GET /api/v1/documents/{id}` (reads the metadata back)
* validation: `application/pdf` content type, `%PDF-` magic bytes, non-empty, 20 MB limit
* upload-then-insert order, with cleanup of the stored file if the insert fails
* `storage_key` is kept internal and is not returned by the API

Tests:

* unit tests with fakes for storage and the database session
* integration tests against the real PostgreSQL and MinIO containers, which skip themselves when those services are not available (so CI stays green)

### Result

```text
PDF
 │
 ▼
POST /api/v1/documents
 │
 ├──► MinIO        documents/<document_id>/<filename>
 │
 └──► PostgreSQL   documents row (filename, storage_key, size, status)
```

### Learning focus

* PostgreSQL
* SQLAlchemy
* Alembic
* object storage
* S3-compatible APIs
* data modeling

### Exit condition

A PDF can be stored in MinIO and its metadata can be stored in PostgreSQL.

**Met:** a real 5.3 MB PDF (the Docling Technical Report) was uploaded through the running API, its row was verified in PostgreSQL and its file in MinIO; fake PDFs and non-PDF files are rejected with the standard error shape; 40 tests pass (36 unit, 4 integration).

---

# Phase 3 — Document Processing Pipeline

### Status

**Complete**

### Objective

Turn uploaded PDFs into structured, meaningful chunks.

### Approach

Exploration came before design. Docling was run on two real PDFs (the Docling Technical Report, a research paper, and ISO/IEC 27001:2022, a policy-style standard), and the chunk schema and cleaning rules were derived from what Docling actually produced, not from assumptions. The throwaway exploration scripts were deleted afterwards; their findings are recorded in `DECISIONS.md` (section 11).

### Completed

Environment:

* Docling 2.133.0 with CPU-only PyTorch (explicit `pytorch-cpu` uv index in `pyproject.toml`)
* uv and Hugging Face caches moved to `D:\Backup\School\Project\_caches\` (`UV_CACHE_DIR`, `HF_HOME`), outside the repository
* `.gitignore`: generated Docling output (`data/sample_docs/output/`) is ignored; `data/eval/` stays trackable

Pipeline (`app/pipeline/`, no FastAPI, Airflow or database imports):

* `models.py`: `Chunk` (text, page_numbers, heading)
* `extract.py`: PDF to Docling document (converter created once and cached)
* `chunk.py`: HybridChunker to `Chunk` objects; table-of-contents chunks dropped by Docling's `document_index` label; nearest heading kept as the section label
* `clean.py`: four rules, each backed by data: remove invisible characters (`\x08`, `\ufeff`), remove the license watermark line, drop chunks that are empty after cleaning, and (in `chunk.py`) drop the table of contents
* `process.py`: `process_pdf(path)` runs extract, chunk, clean

Tests and tooling:

* 19 new unit tests (13 for cleaning, 6 for chunking) using the exact junk strings found in the ISO PDF; no Docling model needed
* `scripts/explore_docling.py` (inspect Docling output for any PDF) and `scripts/run_pipeline.py` (run the real pipeline end to end) kept
* CI stays green with the heavier dependencies

### Result

```text
PDF
 ↓
extract (Docling)
 ↓
chunk (HybridChunker, table of contents dropped)
 ↓
clean (watermark, invisible characters, empty chunks)
 ↓
Chunk(text, page_numbers, heading)
```

Measured results:

* Docling Technical Report: 9 pages, 49 chunks, pages 1 to 9 covered, 88 s on CPU once models are cached
* ISO 27001: 156 raw chunks, 84 of them table-of-contents junk; 72 chunks after the pipeline, with no dot leaders, watermark lines or invisible characters left

(These chunk counts were measured with HybridChunker's default MiniLM tokenizer. Phase 4 switched to the EmbeddingGemma tokenizer, which gives 31 and 58 chunks for the same PDFs.)

### Known limitations (documented, not fixed)

* Text and tables inside embedded images are unreliable (page 8 of the Technical Report is a screenshot of another paper)
* Docling reports every heading as level 1, so only the nearest heading is kept
* Some headings are wrong or missing (a running page header read as a heading; the `9.2` heading of ISO 27001 was missed, so its text sits under `9.1`)
* A table can lose its header row (Annex A of ISO 27001) and can be split across chunks without its caption
* Front-matter chunks (title blocks, author lists) can carry a wrong heading

Phase 7 evaluation will show whether any of these matter enough to fix.

### Learning focus

* document AI
* PDF processing
* document structure
* chunking strategies
* provenance
* diagnosing real-world data before designing

### Exit condition

A real PDF can be processed into useful chunks with page/source information preserved.

**Met:** `process_pdf` ran end to end on the Docling Technical Report (49 chunks with pages and headings), and the same chunk and clean stages produced 72 clean chunks from the ISO 27001 PDF; 59 tests pass or skip (55 passed, 4 integration tests skipped without Docker); CI is green.

---

# Phase 4 — Embedding System

### Status

**Complete**

### Objective

Convert document chunks into semantic vectors.

### Approach

Every unknown was checked before code was written: the model card (prompts, sequence length, dimensions, precision), the installed packages, and the behavior of the model on a few real sentences. Chunk sizes were compared before and after the tokenizer switch, and the whole chain was run on a real PDF before the phase was closed.

### Completed

Environment:

* EmbeddingGemma (`google/embeddinggemma-300m`) loads from the Hugging Face cache on D: through `sentence-transformers` (already installed; no new AI package needed)
* the model is gated: a Hugging Face login (`uv run hf auth login`) is required, because sentence-transformers also downloads small module files
* `pgvector` Python package added (SQLAlchemy `Vector` type and `cosine_distance`)
* one new setting, `EMBEDDING_MODEL_ID`, read by both the chunker tokenizer and the embedding service

Chunking:

* HybridChunker now measures chunk size with the EmbeddingGemma tokenizer (`MAX_CHUNK_TOKENS = 512`)
* tokenizer and chunker are created once and cached

Database:

* migration `3f9a7c2d1e84`: `CREATE EXTENSION vector` and the `document_chunks` table (document_id foreign key with `ON DELETE CASCADE`, chunk_index, text, `page_numbers integer[]`, heading, `embedding vector(768)`, created_at)
* unique constraint on `(document_id, chunk_index)`; no vector index yet (see Phase 5 notes)
* verified with a downgrade and upgrade round trip

Services:

* `EmbeddingService` (`app/services/embeddings.py`): `embed_documents(chunks)` and `embed_query(question)`; the model loads on first use; a dimension check rejects a model whose vectors are not 768-dimensional
* documents are embedded as `title: <heading or none> | text: <chunk text>`; questions use the model's query prompt
* `ChunkService.replace_chunks(document_id, chunks, vectors)` (`app/services/chunks.py`): validates input, then deletes the old chunks and inserts the new ones in one transaction

Tooling and tests:

* `scripts/ingest_document.py`: MinIO to pipeline to embeddings to PostgreSQL for one uploaded document (direct execution mode; Airflow will call the same functions)
* 6 unit tests for the embedding service (fake model), 2 unit tests and 8 integration tests for the chunk service (real PostgreSQL, small fake vectors)
* 75 tests pass, Ruff is clean, CI is green

### Result

```text
documents row + PDF in MinIO
 ↓
process_pdf (Docling, HybridChunker with the EmbeddingGemma tokenizer, clean)
 ↓
EmbeddingService  "title: <heading> | text: <chunk>"
 ↓
768-dimensional normalized vectors
 ↓
ChunkService → document_chunks (pgvector)
```

Measured results:

* chunk size with the EmbeddingGemma tokenizer (same 512 budget, different tokenizer): Technical Report 49 → 31 chunks (average 688 → 1088 characters, 181 → 287 tokens); ISO 27001 72 → 58 chunks (691 → 858 characters, 136 → 169 tokens). The larger vocabulary fits more text into 512 tokens. No chunk exceeds 512 tokens.
* our document format without a heading matches the model's own document prompt exactly (cosine similarity 1.0000); vectors have length 1.0000
* speed on this CPU: 1.6 s per chunk for embeddings (58 ISO chunks in 94 s); the full ingestion of the 9-page Technical Report took 128 s for the pipeline plus 75 s for 31 embeddings, including model loading
* similarity search with pgvector cosine distance on the stored Technical Report: in-scope questions retrieved the right chunk first (similarity 0.55 for tables, 0.58 for OCR); an unrelated question (vacation days) reached only 0.03 to 0.07

### Observations for later phases (not fixed)

* dense search always returns the nearest chunks, even when the document cannot answer; the large gap between in-scope (above 0.5) and unrelated (below 0.1) scores is encouraging, but it was measured on three questions and one document
* a bibliography chunk ranked second for the OCR question; reference lists may add noise
* the second and third results of the table question were only loosely related; with 31 chunks in the document, top-3 includes weak matches

### Learning focus

* embeddings
* semantic representation
* document vs query embeddings
* vector databases
* similarity search concepts

### Exit condition

Document chunks and user queries can consistently be converted into compatible vectors.

**Met:** a real PDF was ingested end to end (31 chunks stored with pages, headings and 768-dimensional vectors), and queries embedded with the same model retrieved the correct chunks through pgvector cosine distance.

---

# Phase 5 — Retrieval System

### Status

**Next**

### Objective

Retrieve the most relevant document chunks for a user question.

### Build

```text
Question
 ↓
Query embedding
 ↓
pgvector similarity search
 ↓
Top-K chunks
```

### Build initially

* cosine/distance-based similarity
* Top-K retrieval
* retrieval service
* metadata preservation
* basic retrieval testing

### Notes from Phase 4

* a throwaway check already proved the query: `DocumentChunk.embedding.cosine_distance(vector)` ordered ascending, joined to `documents` for the file name
* the vectors are normalized, so cosine similarity is `1 - cosine_distance`
* no vector index (HNSW or IVFFlat) is needed at this size; an exact scan is instant and an approximate index would only add approximation. Add one only if search time becomes measurable
* the retrieval result should carry the document id, file name, page numbers, heading, text and similarity, so Phase 6 can build citations without another lookup
* an optional filter by document is cheap now and useful later; add it only if a requirement appears

### Do NOT add yet

* hybrid search
* reranking
* query expansion
* complex retrieval pipelines

### Learning focus

* vector similarity
* retrieval
* Top-K search
* retrieval quality

### Exit condition

Given a test question, the system can retrieve relevant chunks from the correct document.

---

# Phase 6 — Gemini + RAG

### Objective

Turn retrieval into a useful AI assistant.

### Build

```text
Question
 ↓
Retrieval
 ↓
Relevant chunks
 ↓
Context
 ↓
Gemini
 ↓
Grounded answer
 ↓
Citations
```

### Build

* Gemini API integration
* LLM service
* prompt construction
* context construction
* grounded answer generation
* source/page citation output
* basic refusal behavior when relevant information is unavailable

Planning note: vector search never says "nothing found" by itself. Refusal needs either a similarity threshold, the model's own judgement from the prompt, or both. Choose it with evaluation data (Phase 7), not by guessing a number.

### Learning focus

* LLM APIs
* prompting
* RAG architecture
* context management
* grounding
* hallucination control
* citations

### Major milestone

At the end of this phase:

> **The core AI product works.**

A user can ask questions about uploaded company documents and receive grounded answers with citations.

---

# Phase 7 — RAG Evaluation

### Objective

Measure whether the AI system actually works well.

This phase should happen **before advanced RAG optimization**.

### Build

A small evaluation dataset:

```text
Question
Expected answer/information
Expected document
Expected page
```

Store it as JSON or YAML in `data/eval/` (not CSV: `.gitignore` ignores `data/**/*.csv`).

### Evaluate

At minimum:

* retrieval relevance
* correct source retrieval
* citation correctness
* answer grounding
* obvious hallucination cases

Include questions that probe the known Phase 3 limitations (tables, wrongly labelled headings), so the evaluation shows whether they matter.

Also include questions the documents cannot answer, including near misses on the same topic, so the refusal threshold has data behind it.

### Experiments prepared by earlier phases

Each of these is a small, measurable change; none should be made before the evaluation exists:

* heading as the embedding title versus `none` (Phase 4 chose the heading; the evidence is three questions)
* chunk size: 256, 512 or 1024 tokens (`MAX_CHUNK_TOKENS`; the Phase 4 switch to the EmbeddingGemma tokenizer already made chunks about 30 to 60% larger in text)
* Docling's `repeat_table_header` option, for the lost-table-header limitation
* excluding or down-weighting bibliography chunks
* the similarity threshold for "not found"

### Use evaluation to identify weaknesses.

Example:

```text
Evaluation
    ↓
Retrieval misses exact identifiers
    ↓
Investigate hybrid retrieval
```

### Important rule

Do not optimize RAG based on intuition alone.

### Exit condition

There is a repeatable evaluation process that can identify whether a change improves or worsens the system.

---

# Phase 8 — Airflow Orchestration

### Objective

Introduce workflow orchestration without coupling the pipeline to Airflow.

### Build

Airflow DAG:

```text
Extract
   ↓
Clean
   ↓
Chunk
   ↓
Embed
   ↓
Store
```

The DAG calls the existing Python functions: the pipeline in `app/pipeline/`, `EmbeddingService`, and `ChunkService`. `scripts/ingest_document.py` already chains them directly and is the blueprint for the DAG.

Planning notes:

* conversion takes about 10 s per page on CPU, and embedding about 1.6 s per chunk, so a 9-page PDF needs about 3.5 minutes and a 20-page PDF several minutes. Task timeouts and retries must allow for that
* the `documents.status` transitions (`uploaded → processing → processed | failed`) belong to this phase; today the ingestion script leaves the status unchanged
* the Airflow worker needs the Hugging Face token (or a pre-downloaded model volume) for EmbeddingGemma

### Architecture

```text
Airflow
   │
   ▼
Pipeline functions
   │
   ▼
Storage / Database
```

Not:

```text
Airflow
   └── contains all business logic
```

### Learning focus

* DAGs
* tasks
* dependencies
* retries
* scheduling
* workflow orchestration

### Exit condition

The same document-processing logic works both directly and through Airflow.

---

# Phase 9 — Streamlit Interface

### Objective

Create a simple interface for using the system.

### Build

The UI should support:

```text
Upload document
       ↓
View processing status
       ↓
Ask question
       ↓
View answer
       ↓
View sources/pages
```

### Keep it simple

The project is not a frontend project.

Do not spend excessive time on visual design.

### Exit condition

A user can interact with the complete system without directly calling the API.

---

# Phase 10 — Complete Local System

### Objective

Connect all major components into a coherent local application.

### Target

```text
                    USER
                      │
                      ▼
                 Streamlit
                      │
                      ▼
                   FastAPI
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
      MinIO       PostgreSQL      Gemini
                      │
                   pgvector

                   Airflow
                      │
                      ▼
              Document Pipeline
```

### Verify

* document upload
* document processing
* embeddings
* vector storage
* retrieval
* RAG
* citations
* UI
* Airflow
* tests

### Major checkpoint

The complete product works locally from beginning to end.

---

# Phase 11 — Production Containerization

### Objective

Make the application reproducible and portable.

### Build

* production-oriented Dockerfiles
* Docker Compose configuration
* environment-based configuration
* service health checks where useful
* startup behavior
* persistent volumes
* container networking

Planning notes:

* the application image now includes Docling, CPU PyTorch and sentence-transformers, so it will be large. Model downloads (Docling, EmbeddingGemma) need a persistent volume or a build-time step
* EmbeddingGemma is gated: a build-time download or a runtime download needs `HF_TOKEN` as a secret, never baked into an image or committed
* the embedding model loads once per process (about 5 to 10 s); the API must hold one shared `EmbeddingService`, not create one per request

### Verify

A clean environment can start the system using Docker.

### Learning focus

* Docker
* container networking
* container configuration
* reproducible environments

### Exit condition

The application can be run consistently without relying on manually configured local services.

---

# Phase 12 — AWS Deployment

### Objective

Deploy the same application architecture to AWS.

### Initial AWS architecture

```text
Users
  │
  ▼
EC2
├── FastAPI
└── Streamlit
     │
     ├──────────► RDS PostgreSQL
     │              + pgvector
     │
     └──────────► S3
                   documents

External:
Gemini API
```

Supporting services:

```text
IAM
CloudWatch
```

### Principle

Do not redesign the application for AWS.

Map local infrastructure to AWS infrastructure.

```text
MinIO
 ↓
S3

PostgreSQL
 ↓
RDS

Docker application
 ↓
EC2
```

Planning notes:

* the same Alembic migrations run on RDS; `CREATE EXTENSION vector` is supported on RDS PostgreSQL, but the pgvector version is set by the RDS engine version, so check it
* EmbeddingGemma runs on the EC2 CPU: size the instance for the model (about 1.2 GB of weights) plus Docling

### Learning focus

* EC2
* RDS
* S3
* IAM
* CloudWatch
* networking basics
* cloud deployment

### Exit condition

The application is accessible from AWS and the core workflow works remotely.

---

# Phase 13 — Terraform

### Objective

Make the AWS infrastructure reproducible.

### Build

Terraform configuration for the infrastructure that was manually understood during Phase 12.

Potential resources:

* EC2
* RDS
* S3
* IAM
* required networking resources

### Important principle

Terraform comes **after understanding the infrastructure manually**.

The goal is to understand both:

```text
What AWS is doing
```

and

```text
How Terraform describes it
```

### Exit condition

The infrastructure can be recreated from Terraform configuration.

---

# Phase 14 — Production Quality

### Objective

Improve the quality of the complete system without changing the core product unnecessarily.

### Areas

* logging
* error handling
* configuration
* API quality
* test coverage
* evaluation
* monitoring
* documentation
* reproducibility
* deployment reliability

### Possible RAG improvements

Only if evaluation justifies them:

* hybrid retrieval
* reranking
* improved chunking
* prompt improvements
* retrieval filtering
* better citation handling

---

# Phase 15 — Portfolio Preparation

### Objective

Turn the finished project into a strong portfolio artifact.

### Finalize

* README
* architecture diagram
* setup instructions
* deployment instructions
* screenshots
* demo (using an openly licensed document, not the copyrighted ISO standard)
* evaluation results
* technical decisions
* limitations
* future improvements

### README should clearly explain

```text
Problem
   ↓
Solution
   ↓
Architecture
   ↓
AI/RAG pipeline
   ↓
Technology choices
   ↓
Evaluation
   ↓
Deployment
   ↓
Lessons learned
```

The project should be understandable to someone seeing the repository for the first time.

---

# Milestones

The roadmap contains several major milestones.

## Milestone 1 — Backend Foundation

**Reached** (end of Phase 2)

After Phase 2:

```text
FastAPI
+
PostgreSQL
+
MinIO
```

The backend can store documents and metadata.

---

## Milestone 2 — AI Knowledge Pipeline

**Reached** (end of Phase 4)

After Phase 4:

```text
PDF
 ↓
Docling
 ↓
HybridChunker
 ↓
EmbeddingGemma
 ↓
pgvector
```

The system can transform documents into searchable semantic knowledge.

Proof: a real PDF was ingested end to end with `scripts/ingest_document.py`, and a question embedded with the same model retrieved the correct chunk through pgvector.

---

## Milestone 3 — Working AI Assistant

After Phase 6:

```text
Question
 ↓
Retrieval
 ↓
Gemini
 ↓
Grounded answer
 ↓
Citation
```

This is the **most important product milestone**.

---

## Milestone 4 — Evaluated AI System

After Phase 7:

```text
Working RAG
     +
Evaluation
     ↓
Measured quality
```

The system can now be improved based on evidence.

---

## Milestone 5 — Complete Local Product

After Phase 10:

```text
UI
+
API
+
AI
+
Data
+
Storage
+
Airflow
```

The complete application works locally.

---

## Milestone 6 — Cloud Deployment

After Phase 13:

```text
Local
 ↓
Docker
 ↓
AWS
 ↓
Terraform
```

The project demonstrates both AI Engineering and Cloud/DevOps capability.

---

# Priority Rules

When deciding what to work on next, use this priority order:

```text
1. Core AI functionality
2. Core data pipeline
3. Backend integration
4. Evaluation
5. Orchestration
6. User interface
7. Containerization
8. Cloud deployment
9. Infrastructure as Code
10. Advanced improvements
```

If a later phase is blocking understanding of an earlier phase, return to the earlier phase.

Do not jump ahead simply because a technology is interesting.

---

# Definition of Progress

A phase is considered complete when its objective works and can be explained.

"Installed the technology" does not mean the phase is complete.

For example:

```text
Installed Airflow
≠
Airflow phase complete
```

Instead:

```text
Airflow DAG
+
Existing pipeline
+
Successful execution
+
Understanding of orchestration
=
Airflow phase complete
```

The same principle applies to AWS, Terraform, RAG, embeddings, Docker, and other technologies.

---

# What Must Not Happen

The roadmap should prevent the project from becoming unnecessarily large.

Do not:

* jump to AWS before the local application works
* add Kubernetes because it is popular
* add microservices without a real scaling requirement
* add hybrid retrieval without evaluation evidence
* train models unnecessarily
* build an elaborate frontend
* add technologies only for CV keywords
* spend more time designing infrastructure than building the AI system
* postpone the working RAG system because of infrastructure perfection
* build every future feature before validating V1

---

# Final Target

The finished project should demonstrate the following progression:

```text
                    AI ENGINEERING
                          │
                          ▼
             Enterprise Document RAG
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
       AI                DATA             CLOUD
        │                 │                 │
    Gemini            PostgreSQL           AWS
    RAG               pgvector             EC2
    Embeddings        Docling              RDS
    Retrieval         Airflow              S3
    Evaluation        MinIO                Terraform
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                       BACKEND
                          │
                       FastAPI
                          │
                          ▼
                       Docker
```

The final system should be small enough to understand, strong enough to demonstrate real engineering ability, and complete enough to discuss confidently in technical interviews.

> **Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.**
