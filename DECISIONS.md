# DECISIONS.md

## Purpose

This document records important architectural, technical, and product decisions made during the development of the Enterprise AI Document Intelligence Platform.

The goal is to preserve the reasoning behind these decisions so the project remains coherent as it evolves.

A decision may be changed later when new evidence, requirements, or constraints justify it.

---

# 1. Product Decisions

## 1.1 AI Document Intelligence Is the Core Product

**Decision:**
The project focuses on helping employees understand and search enterprise documents using AI.

**Why:**

* Solves a realistic business problem.
* Provides a clear use case for RAG and LLMs.
* Keeps AI Engineering as the main focus.
* Allows Data Engineering, Backend, and Cloud technologies to support one coherent product.

---

## 1.2 V1 Is Intentionally Small

**Decision:**
V1 focuses on:

```text
Upload PDF
    ↓
Process document
    ↓
Create embeddings
    ↓
Store chunks
    ↓
Retrieve relevant chunks
    ↓
Generate answer with Gemini
    ↓
Return answer + citations
```

**Why:**

* Establishes the complete end-to-end AI workflow first.
* Reduces unnecessary complexity.
* Makes the system easier to understand, test, and debug.
* Allows improvements to be based on real evaluation rather than assumptions.

Features such as risk classification, audit prioritization, agents, fine-tuning, and advanced automation are deferred.

---

# 2. Architecture Decisions

## 2.1 Use a Modular Monolith

**Decision:**
The application will initially be built as a modular monolith rather than microservices.

**Why:**

* The project is small enough to operate as one application.
* Easier local development and debugging.
* Lower infrastructure complexity.
* Clear internal module boundaries can be maintained without distributed-system overhead.

Microservices may be considered later only if real requirements justify them.

---

## 2.2 Keep the Document Pipeline Independent

**Decision:**
Document processing logic must remain independent from FastAPI and Airflow.

**Why:**

* The same pipeline should be executable directly during development.
* Airflow should orchestrate the pipeline rather than contain its business logic.
* The pipeline remains easier to test and reuse.

Conceptually:

```text
Pipeline Logic
      ↑
      │
 ┌────┴─────┐
 │          │
Direct    Airflow
Execution  Orchestration
```

Implemented in Phase 3: `app/pipeline/` imports no FastAPI, Airflow, or database code (see section 11). Phase 4 kept this: embedding and storing live in services (`app/services/`), not in the pipeline package (see section 12).

---

## 2.3 Use Direct and Orchestrated Execution Modes

**Decision:**
The system supports two conceptual execution modes.

Development:

```text
FastAPI → Python Pipeline → Storage / Database
```

Orchestrated:

```text
FastAPI → Airflow → Python Pipeline → Storage / Database
```

**Why:**

* Keeps development fast.
* Allows Airflow to provide production-style orchestration.
* Avoids making the core application dependent on Airflow.

Phase 4 implemented the direct mode as `scripts/ingest_document.py` (see 12.10).

---

# 3. AI Decisions

## 3.1 Use Gemini for LLM Generation

**Decision:**
Gemini API is used for answer generation.

**Why:**

* Provides a capable modern LLM without requiring a large local model.
* Fits the project's goal of learning AI integration rather than model training.
* Reduces local hardware requirements.
* Makes the application easier to deploy.

The LLM is treated as an external AI capability integrated into the application.

---

## 3.2 Use EmbeddingGemma for Embeddings

**Decision:**
Use `google/embeddinggemma-300m` for document and query embeddings.

**Why:**

* Can run locally.
* Avoids sending document content to a separate embedding API.
* Provides a practical embedding model for semantic retrieval.
* Produces **768-dimensional embeddings** (confirmed in Phase 4 against the model card and on the real model).

The embedding model can be replaced later if evaluation shows that another model performs better. The model name is one setting (`EMBEDDING_MODEL_ID`), and the database column size is tied to it (see 12.4).

The model is gated on Hugging Face and needs a login (see 12.6). Its weights are in the Hugging Face cache on D: (see 11.3).

---

## 3.3 Start With Dense Retrieval

**Decision:**
Initial retrieval uses vector similarity search with pgvector.

**Why:**

* Simple to implement.
* Appropriate for the initial RAG system.
* Provides a measurable baseline.
* Allows more advanced retrieval techniques to be evaluated later.

Hybrid retrieval, reranking, or other techniques will only be added if evaluation demonstrates a need.

Implemented in Phase 5 as `RetrievalService` (see section 13).

---

## 3.4 RAG Must Be Evaluated Before Optimization

**Decision:**
The first RAG implementation is treated as a baseline.

**Why:**

* Retrieval quality should be measured before adding complexity.
* Improvements should be based on evidence.
* Prevents premature implementation of advanced retrieval techniques.

The evaluation dataset will guide future RAG improvements.

---

# 4. Document Processing Decisions

## 4.1 Use Docling

**Decision:**
Docling is used for document parsing and structured extraction.

**Why:**

* Designed for document understanding.
* Provides structured document representations.
* Better suited to enterprise documents than relying only on basic PDF text extraction.
* Supports preservation of useful document structure.

Phase 3 confirmed this on two real PDFs: prose, headings, page numbers, and the license-free layout of an ISO standard were extracted well. Its limits are recorded in 11.10.

---

## 4.2 Use HybridChunker

**Decision:**
Docling's `HybridChunker` is used as the initial chunking strategy.

**Why:**

* Provides a practical starting point for structured document chunking.
* Works with the structured representation produced by Docling.
* Avoids designing a custom chunking algorithm prematurely.

Chunking strategy can be changed later based on retrieval evaluation.

Phase 3 result (with the default MiniLM tokenizer): chunks averaged 447 to 687 characters, carried page numbers and headings, and skipped page headers and footers by themselves. It keeps a code block intact and writes table cells as `row, column = value`.

Phase 4 result: with the EmbeddingGemma tokenizer the same 512-token budget gives larger chunks (see 12.3).

---

## 4.3 Preserve Document Provenance

**Decision:**
Chunks must retain useful metadata such as document identity, page information, and relevant structural information.

**Why:**

* Enables source citations.
* Makes retrieved information traceable.
* Improves debugging and evaluation.
* Allows the final answer to reference where information came from.

The system should never treat the embedding as a replacement for provenance metadata.

Phase 4 implemented this in the database: `document_chunks` stores the document ID, page numbers, and heading next to each vector (see 12.7). Phase 5 carries it out of the database: every search result keeps the document ID, file name, pages and heading (see 13.1).

---

# 5. Data and Storage Decisions

## 5.1 Use PostgreSQL + pgvector

**Decision:**
PostgreSQL is used as the primary application database and pgvector is used for vector storage.

**Why:**

* One database can store application metadata, document metadata, chunks, and embeddings.
* Reduces infrastructure complexity.
* Avoids introducing a separate vector database without a demonstrated need.
* PostgreSQL is widely used in production systems.

A dedicated vector database may be considered later if scale or requirements justify it.

Phase 4 confirmed that chunks, provenance, and vectors fit in plain PostgreSQL tables (see 12.7). Phase 5 confirmed that one SQL query (cosine distance joined to `documents`) is enough for retrieval (see 13.1).

---

## 5.2 Use MinIO Locally and S3 on AWS

**Decision:**
Original documents are stored in object storage.

Local development:

```text
MinIO
```

AWS deployment:

```text
Amazon S3
```

**Why:**

* Both provide object-storage semantics.
* The application can use a storage abstraction rather than being tightly coupled to one provider.
* Local development remains possible without AWS.
* The same application design can later be deployed to AWS.

---

## 5.3 Separate Documents From Database Data

**Decision:**
Original PDF files are stored in object storage, while metadata, chunks, and embeddings are stored in PostgreSQL.

**Why:**

* Object storage is appropriate for files.
* PostgreSQL is appropriate for structured application data and vectors.
* Keeps responsibilities clear.

---

# 6. Infrastructure Decisions

## 6.1 Docker Is the Portability Layer

**Decision:**
The application and its local infrastructure are containerized with Docker.

**Why:**

* Provides a reproducible development environment.
* Reduces differences between development environments.
* Makes the application easier to deploy.
* Supports the principle of building the application once and deploying it to different environments.

---

## 6.2 Use Docker Compose Locally

**Decision:**
Docker Compose is used for the local multi-service environment.

Initial services include:

```text
FastAPI
Streamlit
PostgreSQL + pgvector
MinIO
Airflow
```

**Why:**

* Easy to start and stop the local environment.
* Appropriate for the project's current scale.
* Avoids unnecessary orchestration infrastructure during development.

---

## 6.3 AWS Comes After the Local System Works

**Decision:**
AWS deployment is a later phase, not a prerequisite for building the application.

**Why:**

* The product should be validated locally first.
* Cloud infrastructure should not hide application problems.
* Development remains cheaper and faster.
* The AWS deployment becomes a deployment exercise rather than a dependency for development.

---

## 6.4 Initial AWS Architecture Is Intentionally Simple

**Decision:**
The initial AWS deployment will primarily use:

```text
EC2
RDS PostgreSQL + pgvector
S3
IAM
CloudWatch
```

**Why:**

* These services are sufficient for the initial application.
* They provide meaningful exposure to compute, database, storage, identity, and monitoring.
* They avoid unnecessary AWS service complexity.

Services such as EKS, Lambda, ECS, OpenSearch, Redis, queues, or complex networking will not be introduced unless the application actually needs them.

---

## 6.5 Terraform Comes After Manual Understanding

**Decision:**
AWS infrastructure will first be understood and tested manually before being fully managed with Terraform.

**Why:**

* Terraform should reinforce infrastructure understanding rather than hide it.
* Makes it easier to understand what Terraform is actually creating.
* Helps with debugging infrastructure problems.

Terraform becomes the infrastructure-as-code layer after the underlying AWS architecture is understood.

---

# 7. Portability Decisions

## 7.1 Same Application, Different Environment

**Decision:**
The application should not be redesigned when moving from local development to AWS.

Conceptually:

```text
Local Environment
    ↓
MinIO
PostgreSQL
Docker
    ↓
Same Application
    ↓
AWS Environment
    ↓
S3
RDS
EC2
```

**Why:**

* Demonstrates proper separation between application logic and infrastructure.
* Reduces deployment-specific code.
* Makes the system easier to maintain.

---

## 7.2 Use Configuration Instead of Hard-Coded Providers

**Decision:**
Environment-specific values such as database URLs, storage endpoints, credentials, and API keys are provided through configuration.

**Why:**

* Keeps secrets out of source code.
* Allows the same application code to run in different environments.
* Supports local development and future AWS deployment.

---

# 8. Engineering Scope Decisions

## 8.1 Do Not Add Technologies Only for the CV

**Decision:**
A technology will only be added when it provides a meaningful technical purpose.

**Why:**

* Technology count is not the goal.
* Coherent engineering is more valuable than a large list of tools.
* Every major technology should be explainable in an interview.

---

## 8.2 Avoid Premature Advanced Infrastructure

**Decision:**
The project will not introduce technologies such as Kubernetes, Kafka, microservices, or dedicated vector databases unless a real requirement appears.

**Why:**

* They increase complexity significantly.
* They are not required for the initial product.
* They can distract from the main AI Engineering objective.

---

## 8.3 Decisions Can Change

**Decision:**
No technology decision is considered permanent.

A decision can be changed when:

* evaluation shows that it is insufficient;
* scale introduces a new requirement;
* a simpler solution becomes available;
* deployment constraints change;
* a real product requirement justifies the change.

The project should evolve based on evidence rather than technology trends.

---

# 9. Backend Application Decisions (Phase 1)

## 9.1 Typed Configuration With pydantic-settings

**Decision:**
All configuration is read into one typed `Settings` object from environment variables and `.env` (`app/core/config.py`). Settings are created once and cached.

**Why:**

* Implements decision 7.2 in practice: nothing environment-specific is hardcoded.
* Values are validated and typed at startup.
* Environment variable names follow the `.env` convention (`APP_ENV`, `LOG_LEVEL`, `DATABASE_URL`).
* Unknown variables are ignored, and each setting is added only when a phase needs it.

---

## 9.2 Use an Application Factory

**Decision:**
The FastAPI app is built by `create_app()` instead of being assembled at import time.

**Why:**

* Tests can build their own isolated app instances.
* Setup (logging, error handlers, routers) happens in one visible place.
* Keeps import-time side effects minimal.

---

## 9.3 Use Standard-Library Logging

**Decision:**
Logging uses Python's built-in `logging` module, configured once in `app/core/logging.py`. The level comes from `LOG_LEVEL`.

**Why:**

* Every module only needs `logging.getLogger(__name__)`.
* No extra dependency is needed for the project's current scale.
* Logging is essential later for debugging which RAG stage failed.

Structured (JSON) logging may be reconsidered for production if there is a real need.

---

## 9.4 One JSON Error Shape

**Decision:**
Every error response uses `{"error": {"code": "...", "message": "..."}}`. Expected failures raise `AppError` subclasses (`NotFoundError`, `ValidationFailedError`, `ExternalServiceError`). FastAPI's own errors (unknown URL, invalid input) use the same shape. Unexpected exceptions return a generic message and are logged in full on the server.

**Why:**

* A UI or client handles one error format.
* Routes do not need their own try/except blocks.
* Exception text can leak internals (paths, SQL, secrets), so it is not sent to clients.

---

## 9.5 Versioned API Prefix; Operational Endpoints Unversioned

**Decision:**
Business endpoints live under `/api/v1`. Operational endpoints (`/health`, `/health/db`) stay at the root.

**Why:**

* A stable URL prefix is cheap now and expensive to change once a UI depends on it.
* Health checks are for infrastructure (Docker, AWS), not API consumers, and should not change with API versions.

---

## 9.6 Thin Routes, Logic in Services

**Decision:**
Routes handle HTTP only. Application logic lives in services (`app/services/`), which are provided to routes through FastAPI dependencies. `InfoService` is the minimal example of the pattern.

**Why:**

* Implements the API-layer rule in ARCHITECTURE.md: no business logic inside route functions.
* Logic can be tested without HTTP.
* Services and pipeline code can be reused by Airflow later.

No base classes or generic abstractions are used until a real need appears.

Phase 5 followed the pattern: the search route is three lines and calls `RetrievalService` (see 13.2).

---

## 9.7 Optional Database URL and Lazy Engine

**Decision:**
`DATABASE_URL` is optional in `Settings`. The SQLAlchemy engine is created on first use, with `pool_pre_ping` enabled. Database health is a separate endpoint (`/health/db`) from basic liveness (`/health`).

**Why:**

* CI and unit tests have no `.env` and no database, so they must still run.
* Code that needs the database fails with a clear message instead of a crash at import time.
* `pool_pre_ping` lets the app recover on its own after the database restarts, which was verified by stopping and starting the Postgres container.
* Liveness (the process is up) and readiness (its dependencies work) are different questions.

---

## 9.8 Test With Dependency Overrides

**Decision:**
Unit tests replace dependencies such as `get_db` with fakes using FastAPI's `dependency_overrides`. Tests that need a real PostgreSQL are integration tests (`tests/integration/`), added in Phase 2 (see 10.8).

**Why:**

* Unit tests stay fast and run anywhere, including CI.
* Error handling can be tested deterministically (for example a simulated database outage).

---

# 10. Data and Storage Application Decisions (Phase 2)

## 10.1 Use boto3 for Object Storage

**Decision:**
Object storage is accessed through `boto3` (the S3 API), not the `minio` SDK. MinIO implements the S3 API, so the same code talks to MinIO locally and Amazon S3 on AWS. When `MINIO_ENDPOINT` is set, boto3 uses it; when it is not set, boto3 talks to real S3 with its default credential chain (an IAM role on EC2).

**Why:**

* Implements decisions 5.2 and 7.1 with configuration only: no provider-specific branches in the code.
* The local environment exercises the same API that AWS will use.
* No extra abstraction layer is needed (see 10.4).

The `MINIO_*` variable names match the Docker Compose file and are kept for now. They may be renamed to neutral `S3_*` names in Phase 12 if that reads better.

Trade-off: if `.env` is missing locally, boto3 would try real AWS instead of failing loudly, so `.env` must be filled in.

---

## 10.2 Alembic for Schema Changes

**Decision:**
Database schema changes are versioned Alembic migrations in `migrations/`, not `Base.metadata.create_all()`. `migrations/env.py` takes the database URL from `Settings`, so `alembic.ini` holds no real URL or password. Generated files in `migrations/versions/` are excluded from Ruff, and every generated migration is read before it is applied.

**Why:**

* `create_all` can create tables but cannot alter them. Later phases need `document_chunks`, a `vector(768)` column, and `CREATE EXTENSION vector`.
* The same migration history will run against RDS in Phase 12.
* One source of truth for configuration (`.env` / environment), as in decision 7.2.
* Autogenerate is a draft, not a guarantee: it targets old-style typing and long lines that the lint rules reject, and hand-editing every future migration would be wasted effort.

The `CREATE EXTENSION vector` migration was deferred to Phase 4, when pgvector was first needed. It is now done (see 12.7).

---

## 10.3 Document Model Choices

**Decision:**
The `documents` table uses a UUID primary key generated in Python, a unique `storage_key`, and a `status` column stored as a plain string (`uploaded`, `processing`, `processed`, `failed`) rather than a PostgreSQL ENUM. No columns are added before a phase needs them.

**Why:**

* The upload code needs the document ID before the insert, to build the storage key.
* UUIDs cannot be guessed from the URL, unlike sequential integers.
* ENUM types are awkward to change in migrations; the application enforces the allowed values.
* Phase 3 will show which extra fields (for example an error message or page count) are really needed.

Phase 3 outcome: the pipeline did not need any new `documents` column. Phase 4 did not need one either, and neither did Phase 5. If Phase 8 needs an error message or page count, it is added then.

---

## 10.4 A Small Storage Service

**Decision:**
`StorageService` (`app/services/storage.py`) has three methods: `upload`, `download`, `delete`. It is the only code that imports boto3. It works with `bytes`, builds its client lazily and caches it, and maps boto3 errors to `NotFoundError` (missing key) and `ExternalServiceError` (anything else). The application does not create the bucket; the `minio-init` container in Docker Compose does.

**Why:**

* Abstract real variation, not imaginary future variation (ENGINEERING_PRINCIPLES 14): no interface class or plugin system.
* Routes and the pipeline never see boto3 exceptions.
* The lazy client lets the app and CI start without storage settings.
* Passing the client in the constructor lets unit tests use a fake with no network.

Limitation: files are handled as `bytes` in memory. This is acceptable with a 20 MB upload limit; streaming is a future improvement if file sizes require it.

---

## 10.5 Upload Order: Validate, Store the File, Then Insert the Row

**Decision:**
`DocumentService.create` validates the file, uploads it to storage, then inserts the database row. If the insert fails, it rolls back and deletes the uploaded file (best effort). If the upload fails, no row is created.

**Why:**

* A row that points to a missing file is worse than a stored file without a row.
* Cleanup keeps storage and database consistent in the common failure cases.
* The cleanup path is verified against real services by an integration test.

Known limit: if the process crashes between the two steps, an orphaned file can remain. A periodic cleanup job is not justified at the current scale.

---

## 10.6 Upload Validation and Storage Keys

**Decision:**
An upload is accepted only if its content type is `application/pdf`, its bytes start with `%PDF-`, it is not empty, and it is within `MAX_UPLOAD_MB` (default 20). The storage key is `documents/<document_id>/<filename>`, where the filename is reduced to its last path component and limited to 255 characters. `storage_key` is internal and is not returned by the API.

**Why:**

* A client can lie about the content type, so the file itself is checked.
* The UUID in the key prevents collisions when two people upload `policy.pdf`, and keeps the original name readable in MinIO.
* Browsers can send full paths, which must not become part of the key.
* Hiding `storage_key` keeps storage details out of the API contract.

---

## 10.7 Document Endpoints

**Decision:**
`POST /api/v1/documents` stores a PDF and returns its metadata (`201`). `GET /api/v1/documents/{id}` returns the metadata of one document. Both follow the thin-route rule (9.6). Multipart uploads need the `python-multipart` package.

**Why:**

* Completes the Phase 2 exit condition through the real API.
* The GET endpoint costs almost nothing and lets us verify stored rows.

---

## 10.8 Integration Tests Skip When Services Are Unavailable

**Decision:**
Tests in `tests/integration/` use the real PostgreSQL and MinIO containers. They skip themselves when `DATABASE_URL` or `MINIO_ENDPOINT` is not set, or when a service is not reachable. Each test removes only the rows and files it created.

**Why:**

* CI has neither service and must stay green; unit tests with fakes cover the logic there.
* Fakes cannot catch wrong column types, a broken unique constraint, or bad storage keys. Integration tests can.
* Cleaning only what a test created keeps real local data safe.

Phase 4 followed this for chunks: the `db` fixture deletes the documents a test created, and the database cascade removes their chunks (see 12.8). Phase 5 followed it for retrieval: the test document is created and deleted by a fixture, and the real Technical Report in the database is never touched (see 13.8).

---

# 11. Document Processing Decisions (Phase 3)

## 11.1 Look at Real Output Before Designing

**Decision:**
Before writing any pipeline code, Docling was run on two real PDFs and its output was inspected: pages, headings, tables, chunks, content layers, and control characters. The chunk schema and the cleaning rules come from those measurements. The throwaway inspection scripts were deleted afterwards; only `scripts/explore_docling.py` and `scripts/run_pipeline.py` were kept.

**Why:**

* `PROJECT.md` says the metadata schema should be based on what the libraries actually provide, not on invented fields.
* Several assumptions were wrong until measured: the first sample (a research paper) turned out to contain screenshots of another paper, and picture text never reached the chunks.
* The two samples were different on purpose. A research paper (Docling Technical Report, 9 pages) and a policy-style standard (ISO/IEC 27001:2022, 26 pages) behave very differently, and the second one is closer to the project's target content.

---

## 11.2 CPU-Only PyTorch Through an Explicit uv Index

**Decision:**
Docling is installed together with `torch` and `torchvision` listed as direct dependencies. `pyproject.toml` points both to an explicit `pytorch-cpu` index (`https://download.pytorch.org/whl/cpu`, `explicit = true`).

**Why:**

* The GTX 1050 has 4 GB of VRAM, too little to be useful for Docling's models, and the CUDA build adds several GB for no benefit.
* `[tool.uv.sources]` only applies to packages listed directly, so `torch` must be a direct dependency for the setting to work.
* On Linux, PyPI's `torch` is the CUDA build, so without this setting GitHub Actions would download CUDA libraries it cannot use. CI stayed green with this setup.
* `explicit = true` means that index is used only for the packages named in `sources`.

Measured speed on this CPU once models are cached: about 10 s per page (88 s for 9 pages). The first runs took 311 to 338 s, because they included model downloads.

---

## 11.3 Caches Live on D:, Outside the Repository

**Decision:**
`UV_CACHE_DIR` and `HF_HOME` are user environment variables pointing to `D:\Backup\School\Project\_caches\uv` and `D:\Backup\School\Project\_caches\huggingface`. The old uv cache on C: was cleaned. The EmbeddingGemma model already downloaded on C: was moved, not downloaded again.

**Why:**

* C: (the SSD) had about 17 GB free; Docling, PyTorch and the models need several GB.
* uv uses hardlinks only within one drive. With the cache and `.venv` both on D:, PyTorch is stored once instead of twice.
* The `_caches` folder is outside the repository, so it cannot be committed by accident.

Harmless side effect: Hugging Face warns that Windows has no symlink support, so its cache uses somewhat more space.

Phase 4 note: the Hugging Face login token is saved under `HF_HOME` too, so it is also outside the repository (see 12.6).

---

## 11.4 Chunk Schema From What Docling Provides

**Decision:**
The pipeline's `Chunk` is a frozen dataclass with three fields: `text`, `page_numbers` (a list of ints), and `heading` (a string or `None`). `document_id` and `embedding` are not part of it: the document ID is attached when chunks are stored, and the embedding is produced by the embedding service.

**Why:**

* `chunk.meta.doc_items` carries page numbers per item, and `chunk.meta.headings` carries the headings. Nothing was invented.
* Chunks can span pages (for example pages 2 and 3), so a single page number would be wrong for citations. A citation can show a range.
* A plain dataclass keeps the pipeline free of Docling, FastAPI, and database types.

Phase 4 kept this schema unchanged: `ChunkService` receives the document ID from its caller, and `EmbeddingService` returns plain lists of floats next to the chunk list.

---

## 11.5 Keep Only the Nearest Heading

**Decision:**
`heading` is the last entry of `chunk.meta.headings`. No heading hierarchy is built.

**Why:**

* Docling reported every heading as level 1 on both PDFs ("3.1 PDF backends" and "Abstract" alike), so heading levels are unreliable.
* The heading text itself ("6.1.2 Information security risk assessment") is a good section label for a citation.

---

## 11.6 Four Cleaning Rules, Each Backed by Data

**Decision:**
The pipeline applies exactly these rules:

1. Drop chunks that come from the table of contents (11.7).
2. Remove the license watermark line (a line starting with `--` made of backticks, commas and hyphens, at least 15 characters and containing a backtick).
3. Strip the invisible characters `\x08` (backspace) and `\ufeff` (byte-order mark) from text and headings.
4. Drop chunks that are empty after cleaning.

**Why:**

* The ISO PDF produced 156 chunks; 84 were table-of-contents lines with dot leaders, 95 contained control characters (84 of them in the table of contents), and 14 contained the watermark. After the rules, 72 chunks remain (measured with the MiniLM tokenizer; 58 with the EmbeddingGemma tokenizer, see 12.3), with no dot leaders, watermarks or invisible characters.
* `\x08` is invisible in a UI but would end up in the database, in the embedded text, and in the prompt sent to Gemini.
* The watermark appeared as body text on most pages and as a page footer on some, so it cannot be removed by content layer alone.
* The watermark pattern requires a backtick so that an ordinary line of dashes is never removed (covered by a unit test).

Page headers and footers need no rule: Docling puts them in the `FURNITURE` layer and the chunker skips them. Text inside pictures needs no rule either: only 2 of 88 items in the ISO chunks sat inside a picture, while 684 picture-text items existed in the Technical Report, and almost none reached the chunks.

---

## 11.7 Filter the Table of Contents After Chunking, by Label

**Decision:**
`chunk_document` drops any chunk whose `doc_items` include an item labelled `document_index`. The Docling document itself is not modified.

**Why:**

* Docling labels the table of contents `document_index` (a 47-row table, 60,335 characters as Markdown), so a label check is more reliable than a text pattern.
* Filtering after chunking is simpler and leaves Docling's objects untouched. It costs 84 chunks built and thrown away, which is negligible.
* This is the source of the very long table-of-contents chunk that triggers the chunker's token-length warning (16,494 tokens with MiniLM, 2,380 with the EmbeddingGemma tokenizer). The warning is harmless: the chunker only counts tokens, no model reads that text, and the chunk is dropped.
* The rule only works when Docling detects the table of contents. A PDF whose contents page is not detected would keep its dot-leader chunks; Phase 7 evaluation or a new sample would show it.

---

## 11.8 No Minimum Chunk Size

**Decision:**
Only chunks that are empty after cleaning are dropped. There is no length threshold.

**Why:**

* There is no evidence that small chunks hurt retrieval. The smallest real chunk was 11 characters (`(normative)`), which is harmless.
* A threshold would be a tuning knob without data (ENGINEERING_PRINCIPLES 11). If Phase 7 shows tiny chunks hurt, we add it then.

---

## 11.9 Pipeline Structure: Small Stages, Injectable Chunker

**Decision:**
`app/pipeline/` holds `models.py`, `extract.py`, `chunk.py`, `clean.py`, and `process.py`. `process_pdf(path)` chains extract, chunk, clean. The Docling converter is created once and cached, because building it loads models. `chunk_document` takes an optional chunker argument.

**Why:**

* Each stage is understandable and testable alone (ENGINEERING_PRINCIPLES 7), and Airflow can later call the same functions.
* `clean.py` is made of pure functions, so its 13 tests need no Docling and run in a fraction of a second, using the exact junk strings found in the real PDFs.
* The injectable chunker lets the 6 chunk tests use fake chunks, so no model is loaded.

Scripts that import from `app` run as modules (`uv run python -m scripts.run_pipeline`), because running a file directly puts only the `scripts/` folder on the Python path.

---

## 11.10 Known Limitations Accepted for Now

**Decision:**
These problems were found and are documented, not fixed:

* **Text and tables inside embedded images are unreliable.** Page 8 of the Technical Report is a screenshot of another paper; Docling read it as page text, which produced duplicated paragraphs and badly structured tables with OCR errors. No code filter exists for this.
* **Some headings are wrong or missing.** A running page header (`ISO/IEC 27001:2022(E)`) was read as a heading on pages 8 and 14, and the `9.2` heading was missed, so the 9.2.1 text sits under `9.1`. Front-matter chunks can carry a wrong heading (for example `Version 1.0` for an author list).
* **Tables can lose their header row** (Annex A of ISO 27001 shows `5.12, 1 = Classification...`), and a table can be split across chunks, so the second part has no caption. The text and the control IDs remain retrievable.
* **Rows without a separator line merge** (Table 1 of the Technical Report shows `4 16` and `177 s 167 s`). All the data is present.

**Why:**

* The sample corpus is policy-style prose, where these cases are rare. A rule such as "ignore a heading that repeats on several pages" would also remove legitimate repeated captions like `Table A.1 (continued)`.
* Advanced table options or heavier models were rejected: the one real table was already acceptable, and no setting makes 5 pt screenshots readable.
* Phase 7 evaluation will show whether any of these affect answers and citations. Questions about tables and mislabelled sections should be part of the evaluation dataset.

Phase 4 note: because the heading is now part of the embedded text (12.2), a wrong heading can slightly mislead a vector. The Phase 7 experiment "heading versus `none`" tests this.

Phase 4 also found a candidate fix to try in Phase 7: HybridChunker has a `repeat_table_header` option that repeats a table's header in every chunk of that table.

---

## 11.11 The Chunker and the Embedding Model Use the Same Tokenizer

**Decision:**
HybridChunker measures chunk size with the tokenizer of the embedding model (`EMBEDDING_MODEL_ID`, EmbeddingGemma), with a 512-token budget. Implemented in Phase 4 (`app/pipeline/chunk.py`). How the text is formatted for embedding is decided in 12.2.

**Why:**

* Chunk size should be measured with the tokenizer of the model that embeds the chunks; token counts differ between tokenizers. The Docling documentation says the same.
* The MiniLM tokenizer was used only during Phase 3 as HybridChunker's default and is not used anywhere else.

The effect on chunk sizes is recorded in 12.3.

---

## 11.12 Sample Documents Stay Local

**Decision:**
Sample PDFs and Docling output stay in `data/sample_docs/`, which is git-ignored (`data/**/*.pdf` and `data/sample_docs/output/`). `data/eval/` stays trackable. The ISO/IEC 27001 standard is copyrighted and is used locally only.

**Why:**

* The repository is public and must not contain third-party copyrighted documents or large generated JSON.
* The final demo and the Phase 7 evaluation dataset need an openly licensed document.
* The evaluation dataset should be JSON or YAML, because `.gitignore` also ignores `data/**/*.csv`.

---

# 12. Embedding Decisions (Phase 4)

## 12.1 Check the Model Card Before Writing Code

**Decision:**
Before writing the embedding service, the model card, the installed packages, and the model's behavior on a few sentences were checked. Only then was code written.

**Why:**

* Three assumptions were open at the start of the phase: the prompts, the maximum input length, and the installed packages.
* The model card answered them: queries and documents use different prompts, the input limit is 2048 tokens, vectors are 768-dimensional (smaller sizes are possible through Matryoshka truncation), and `float16` is not supported (use `float32` or `bfloat16`).
* `sentence-transformers` and `transformers` were already installed (through Docling and earlier work), so no AI package had to be added. Only the small `pgvector` package was new (see 12.7).

Two short checks confirmed the behavior on this machine: 768 dimensions, max sequence length 2048, normalized vectors (norm 1.0000), and the right document ranked first with and without prompts. With prompts the margin was larger (3 sentences only, an illustration, not evidence).

---

## 12.2 Embed `title: <heading> | text: <chunk>`, Built by Our Own Code

**Decision:**
A chunk is embedded as the string `title: {heading or "none"} | text: {chunk text}`. The string is built by `build_document_text` in `app/services/embeddings.py` from our own `Chunk`, and passed to the model's plain `encode`. Questions use the model's `encode_query`.

**This replaces** the earlier plan (Phase 3 version of this decision) to embed `chunker.contextualize(chunk)`.

**Options considered:**

| | A. `chunker.contextualize(chunk)` | B. Build the string ourselves (chosen) |
|---|---|---|
| Where it happens | In the chunking stage, needs the raw Docling chunk | In the embedding stage, needs only our `Chunk` |
| Effect on `Chunk` | Either pollutes `text` with the heading or needs a new field | None |
| Pipeline independence | The embed stage would depend on Docling objects | The embed stage works on plain data |
| Format | Docling's own (heading, newline, text) | The model's native `title: ... \| text: ...` |

**Why B:**

* The model was trained with a document prompt that has a title slot, and the model card says a real title improves quality.
* The model's own `encode_document` always writes `title: none`, so it cannot carry our heading. Building the string ourselves can.
* `Chunk` stays unchanged and the embedding stage stays independent of Docling (decisions 2.2 and 11.4).
* Verified: without a heading, our string gives the same vector as the model's own `encode_document` (cosine similarity 1.0000).

**Known trade-off:** some headings are wrong (11.10), and a wrong title can slightly mislead the vector. The Phase 7 experiment "heading versus `none`" will measure it.

The stored `text` column holds the plain chunk text, not the formatted string. The formatted string is only what the model sees, and it is rebuilt from `heading` and `text` when needed.

---

## 12.3 Keep 512 Tokens; Chunks Became Larger

**Decision:**
`MAX_CHUNK_TOKENS` stays 512 after switching to the EmbeddingGemma tokenizer, even though the model accepts 2048. Chunk size is tuned later, with evaluation data.

**What happened:**

| Document | MiniLM (Phase 3) | EmbeddingGemma |
|---|---|---|
| Technical Report | 49 chunks, avg 688 chars, 181 tokens | 31 chunks, avg 1088 chars, 287 tokens |
| ISO 27001 | 72 chunks, avg 691 chars, 136 tokens | 58 chunks, avg 858 chars, 169 tokens |

Both rows were measured with the EmbeddingGemma tokenizer as the ruler. No chunk exceeds 512 tokens.

**Why:**

* MiniLM has a small vocabulary and splits text into many tokens; EmbeddingGemma has a much larger one. The same 512-token budget therefore holds 30 to 60% more text.
* An average of 170 to 290 tokens is a normal RAG chunk size and far below the model's 2048 limit.
* There is no evidence that a different size is better. Chunk size (for example 256 versus 512 versus 1024) is a Phase 7 experiment and a one-line change.

Earlier statements that the switch would "keep chunks close to Phase 3" were wrong; the number stayed the same but the amount of text did not.

---

## 12.4 One Model Setting, One Dimension Check

**Decision:**
The embedding model is the single setting `EMBEDDING_MODEL_ID` (default `google/embeddinggemma-300m`), read by both the chunker tokenizer and the embedding service. `EmbeddingService` checks the model's output size against `EMBEDDING_DIMENSIONS` (768, defined next to the database model) when the model loads, and raises a clear error if they differ.

**Why:**

* The chunker's tokenizer and the embedding model must always be the same model (11.11). One setting prevents two copies from drifting apart.
* The database column is `vector(768)`. Setting a different model in the environment would otherwise fail later with a confusing database error.
* Changing to a model with another size needs a new migration. The check makes that visible immediately.

---

## 12.5 EmbeddingService: Lazy Loading, CPU, Separate Methods

**Decision:**
`EmbeddingService` (`app/services/embeddings.py`) has `embed_documents(chunks)` and `embed_query(question)`. The model is loaded on first use, on CPU. The constructor accepts a model, so unit tests pass a fake.

**Why:**

* Importing `sentence_transformers` loads torch, which takes seconds. Lazy loading keeps imports and unit tests fast and lets CI run without the model.
* Documents and queries need different formats (12.2), so they are separate methods and the caller cannot mix them up.
* The GTX 1050 (4 GB) is not used; the model is small and the CPU is enough (1.6 s per chunk).
* The 6 unit tests use a fake model; no download is needed.

The API now holds one shared instance for all requests (done in Phase 5, see 13.3).

Measured speed: 58 ISO chunks in 94 s (1.6 s per chunk); 31 chunks of the Technical Report in 75 s including model loading.

---

## 12.6 The Gated Model Needs a Hugging Face Login

**Decision:**
EmbeddingGemma requires accepting Google's license and logging in (`uv run hf auth login`). The token lives under `HF_HOME` on D:, outside the repository.

**Why:**

* Loading the weights through `transformers` had worked earlier, but `sentence-transformers` also downloads small module files (for example `4_Normalize/config.json`), and the gated repository answered those requests with 401 until a login existed.
* The fix is authentication, not code. It downloads only a few tiny files, not the 1.2 GB weights again.

Consequences for later phases (recorded in ROADMAP.md):

* Docker image and Airflow worker (Phases 8 and 11): `HF_TOKEN` as a secret in the environment, or models pre-downloaded into a volume. Never baked into an image or committed.
* AWS (Phase 12): the same, through the deployment's secret mechanism.
* CI never needs it, because tests use fakes and the model loads lazily.

---

## 12.7 The `document_chunks` Table

**Decision:**
Migration `3f9a7c2d1e84` enables pgvector (`CREATE EXTENSION IF NOT EXISTS vector`) and creates `document_chunks`:

* `id`: UUID primary key, generated in Python (same pattern as `documents`)
* `document_id`: foreign key to `documents.id` with `ON DELETE CASCADE`
* `chunk_index`: integer, the chunk's order in the document
* `text`: the chunk text
* `page_numbers`: PostgreSQL `integer[]`
* `heading`: text, nullable
* `embedding`: `vector(768)`, NOT NULL
* `created_at`: set by the database
* a unique constraint on `(document_id, chunk_index)`

No vector index (HNSW or IVFFlat) is created.

**Why:**

* Cascade: deleting a document removes its chunks, so no orphans are possible. Tested against the real database.
* `integer[]` stores the page range of a chunk without a join table (chunks can span pages).
* `NOT NULL` plus `vector(768)`: the database rejects a missing or wrong-sized vector, which implements "vector dimension validation" with no extra code.
* The unique constraint stops duplicate chunks when a document is processed twice. Its index also serves "all chunks of a document", so a separate index would be redundant.
* No vector index: with about 30 to 60 chunks per document an exact scan is instant. An approximate index would make results approximate for no benefit. It is added only if search time becomes measurable.
* The migration was written by hand (autogenerate does not produce `CREATE EXTENSION`) and read before it was applied. `upgrade` creates the extension first, then the table; `downgrade` does the reverse. A downgrade and upgrade round trip was verified. RDS PostgreSQL supports the same `CREATE EXTENSION`, so the migration will run there too (Phase 12).
* The `pgvector` Python package provides the `Vector` column type and `cosine_distance`. It is a small package; the database extension is separate.

The pre-commit secret scanner flagged the random hex revision IDs of the migration as a possible secret. The fix is an inline `# pragma: allowlist secret` comment on those two lines, not a rule that disables the scanner for the whole migrations folder, so a real secret pasted into a migration would still be caught.

---

## 12.8 ChunkService: Replace in One Transaction, Validate First

**Decision:**
`ChunkService.replace_chunks(document_id, chunks, vectors)` (`app/services/chunks.py`):

1. Validates that the number of chunks equals the number of vectors and that every vector has 768 values. A mismatch raises `ValueError` before anything is touched.
2. Raises `NotFoundError` if the document does not exist.
3. Deletes the document's old chunks and inserts the new ones in one transaction. Any failure rolls back, so the old chunks survive.
4. Returns how many chunks were stored. An empty list clears the document's chunks.

The document ID comes from the caller; `documents.status` is not changed.

**Why:**

* Replace, not append: processing a document twice must not create duplicates, and a half-written document must never be visible.
* A count or size mismatch is a bug in the caller, not a user error, so it is a `ValueError`, not an API error.
* A clear `NotFoundError` is better than a foreign-key error from the database.
* Embedding (the model) and storing (the database) are different responsibilities. Separate services keep the storage code testable without loading the model.
* The status transitions (`uploaded → processing → processed | failed`) belong to orchestration (Phase 8).

Tests: 2 unit tests (input rejected before anything is deleted) and 8 integration tests on the real PostgreSQL with small fake vectors: provenance and vectors round trip, replace removes old chunks, empty replacement, cascade on document deletion, rejected input keeps old chunks, unknown document, failed commit keeps old chunks, one row per `(document, chunk_index)`. The failed-commit test is the one that proves the transaction behavior.

---

## 12.9 Cosine Distance on Normalized Vectors

**Decision:**
Similarity search uses pgvector's cosine distance. Similarity is reported as `1 - cosine_distance`.

**Why:**

* The model outputs vectors of length 1.0000, so cosine similarity and dot product rank identically.
* Cosine is the standard choice and stays correct if the embedding model is replaced by one that does not normalize.

The query shape was proven in Phase 4 with a throwaway check: order by `DocumentChunk.embedding.cosine_distance(query_vector)`, join to `documents` for the file name. The real retrieval service is in Phase 5 (see 13.1).

---

## 12.10 Direct Ingestion Script, No New Service Class

**Decision:**
`scripts/ingest_document.py <document_id>` runs the whole chain for an uploaded document: download the PDF from storage, `process_pdf`, `embed_documents`, `replace_chunks`. It is kept in the repository. It does not change `documents.status`, and there is no "ingestion service" class.

**Why:**

* It is the direct execution mode of decision 2.3, and the blueprint for the Phase 8 Airflow tasks, which will call the same functions.
* A script that chains four calls does not need a class yet (ENGINEERING_PRINCIPLES 14).
* Running it again replaces the chunks, so it is safe to repeat.

Verified on the Technical Report: 31 chunks stored (the same count as the earlier comparison), 768 dimensions on every row, a chunk spanning pages `{1,2}` stored correctly as an array. Timing: 128 s for the pipeline plus 75 s for embeddings.

---

## 12.11 Dense Search Never Says "Not Found"

**Observation (not a decision to fix yet):**
Vector search always returns the nearest chunks, even when the document cannot answer.

Measured on the stored Technical Report with three questions:

* in-scope, tables: top similarity 0.55 (correct chunk first);
* in-scope, OCR: top similarity 0.58 (correct chunk first, a bibliography chunk second at 0.43);
* unrelated (vacation days): top similarity 0.07.

**Why this matters:** refusing to answer needs a similarity threshold, the LLM's own judgement from the prompt, or both. The gap between in-scope and unrelated scores is encouraging, but it was measured on three questions and one document, so no threshold is chosen now. The threshold and the refusal behavior are set with evaluation data in Phases 6 and 7, including questions the documents cannot answer and near-miss questions on the same topic.

Other observations carried to Phase 7: bibliography chunks can rank high for questions that mention a cited tool; the second and third results of a question can be only loosely related when a document has few chunks.

Phase 5 reproduced the same numbers through the API and added no new observation that changes this decision (see 13.9).

---

# 13. Retrieval Decisions (Phase 5)

## 13.1 RetrievalService Returns Plain Objects, Not Database Rows

**Decision:**
`RetrievalService.search(question, top_k)` (`app/services/retrieval.py`) embeds the question with `EmbeddingService.embed_query`, runs one pgvector query, and returns a list of `RetrievedChunk`. `RetrievedChunk` is a frozen dataclass with `document_id`, `filename`, `page_numbers`, `heading`, `text` and `similarity`. The query orders `document_chunks` by cosine distance to the query vector, joins `documents` for the file name, and takes the top K. The service takes the database session and the embedding service as constructor arguments.

**Options considered:**

| | A. Plain result object (chosen) | B. Return `DocumentChunk` rows |
|---|---|---|
| What the caller receives | Only the fields it needs | The whole ORM object, including the 768-number vector |
| Coupling | None to SQLAlchemy | Every caller depends on the database layer |
| File name for citations | Included (joined in the query) | A second lookup per hit |
| Testing callers | Build a dataclass | Build ORM objects |

**Why A:**

* Phase 6 builds citations from exactly these fields, so it needs no second lookup. This implements decision 4.3 (provenance) on the way out of the database.
* The vector is never needed after the search, and callers should not see it.
* It follows the same idea as 11.4: plain dataclasses between layers. The API gets its own Pydantic schema, as with `DocumentResponse`.
* This is a common industry pattern (services return their own data types instead of database rows); small projects sometimes skip it, so it is a trade-off, not a law.

The same service takes a fake embedding service in tests, so ranking can be tested with hand-made vectors and no model (see 13.8).

---

## 13.2 A `POST /api/v1/search` Inspection Endpoint

**Decision:**
`POST /api/v1/search` accepts `{question, top_k}` and returns `{results: [...]}`, where each result has the `RetrievedChunk` fields. The route is thin (9.6): it calls `RetrievalService` and converts the results to the Pydantic response. It is an inspection endpoint, not the product's question endpoint; the answer endpoint (`/ask`) arrives in Phase 6 and does not replace it.

**Why:**

* Without it, retrieval could only be tried from a script. With it, a question can be typed into `/docs` and the chunks seen at once.
* It supports ENGINEERING_PRINCIPLES 19 (debug the root cause): when a later answer is bad, the same question can be sent to `/search` to see whether retrieval or generation is at fault.
* It costs about 30 lines. The Phase 9 UI or the Phase 7 evaluation can reuse it.
* It is a POST because the question travels in the request body.

It was optional, and was added because it gives the first real end-to-end check of Phase 5 through the API.

---

## 13.3 One Shared EmbeddingService, Loaded Lazily, Behind a Plain `def` Route

**Decision:**
`app/api/deps.py` provides `get_embedding_service`, decorated with `lru_cache`, so the process creates one `EmbeddingService`. The model inside it still loads on first use (12.5), so the first search pays the loading time. The search route is a plain `def`, not `async def`.

**Options considered for loading time:**

| | Lazy (chosen) | Preload at startup |
|---|---|---|
| Server start | Instant; `/health` and tests are unaffected | Seconds slower; fails early if the Hugging Face login or model is missing |
| First search | Slower, once | Fast |
| Tests and CI | No change | Every `create_app()` would need a model override |

**Why lazy:**

* It keeps startup, `/health` and every existing test simple.
* Preloading only matters when the container health check and startup behavior are designed. It is revisited in Phase 11, where it becomes a real question.

**Why one instance:** the model takes seconds to load and uses memory, so it must never be created per request.

**Why `def` and not `async def`:** embedding is blocking CPU work. In an `async def` route it would freeze the event loop and stop every other request. FastAPI runs `def` routes in a thread pool, so the server stays responsive. The document routes already use `def` for the same reason.

**Known trade-offs:**

* Two simultaneous first requests could both load the model, because there is no lock. For one developer this only wastes time, so no locking code is added (ENGINEERING_PRINCIPLES 3).
* Measured: the first request took about 22 s (not the 5 to 10 s estimated earlier). The load makes about 15 requests to huggingface.co to check for updates even though the files are cached. In Phase 11 the containers should run offline with the model pre-downloaded.
* `uvicorn --reload` restarts the process on code changes, so the model loads again on the next first search.

---

## 13.4 Input Limits: `top_k` 1 to 20 (Default 5), Question 1 to 1000 Characters

**Decision:**
`top_k` defaults to 5 and must be between 1 and 20. The question is stripped of surrounding whitespace and must be between 1 and 1000 characters.

**Why:**

* Without a maximum `top_k`, a client could ask for 100,000 chunks and slow the database.
* An empty question cannot be embedded in a useful way.
* The model accepts up to 2048 tokens, so 1000 characters is a safe, simple guard.
* The numbers are guesses, not measurements (ENGINEERING_PRINCIPLES 12). They are listed as Phase 7 experiments (ROADMAP.md): the right `top_k` depends on how many chunks the prompt should carry, which only evaluation can show.

An empty database or a question with no match returns an empty list, not an error.

---

## 13.5 Limits Live in the Service; Two Layers Check Them

**Decision:**
`DEFAULT_TOP_K`, `MAX_TOP_K` and `MAX_QUESTION_CHARS` are constants in `app/services/retrieval.py`. The Pydantic schemas in `app/schemas/search.py` import them, and the request model strips whitespace before checking length. The API therefore rejects bad input with `422 validation_failed` (the standard error shape, through the existing validation handler) before the service runs. The service validates again and raises `ValueError`.

**Why:**

* The limits are defined once, so the API and the service cannot drift apart.
* The API check gives users a clean 422. The service check protects the service from other callers (a script, the Phase 6 RAG service, Airflow).
* A bad value reaching the service is a bug in the caller, not a user mistake, so it is a `ValueError`, the same rule as 12.8.

Known gap: `ValueError` is not mapped to an HTTP error. Through `/search` it cannot happen, because the schema checks first. A future endpoint that skips the schema would return a generic 500. This is accepted until such an endpoint exists.

---

## 13.6 Stable Ordering With Tie-Breakers

**Decision:**
The query orders by distance, then `document_id`, then `chunk_index`.

**Why:**

* If two chunks have exactly the same distance, the database may return them in any order, and the order can change between runs.
* A stable order makes tests and later evaluation repeatable (ROADMAP Phase 7 exit condition).
* It costs nothing, and does not change the result when distances differ.

---

## 13.7 Still Deferred: Threshold, Document Filter, Vector Index, Hybrid Search

**Decision:**
Phase 5 adds none of these:

* **Similarity threshold for "not found":** chosen with evaluation data (Phases 6 and 7), as decided in 12.11. The service returns the similarity of every hit, so the threshold can be applied later without changing the service's shape.
* **Filter by document:** no requirement exists; it is a small change if one appears.
* **HNSW or IVFFlat index:** an exact scan is instant at tens of chunks per document, and an index would make results approximate for no benefit (12.7).
* **Hybrid search, reranking, query expansion:** only if evaluation shows dense retrieval fails (decisions 3.3 and 3.4).

**Why:**

* "Evaluate before optimizing" (ENGINEERING_PRINCIPLES 11): the only data so far is three questions on one document.

---

## 13.8 Tests: Hand-Made Vectors, and Test Files Need Unique Names

**Decision:**
The retrieval service is tested at three levels:

* 7 unit tests (parametrized) check that an empty or too long question and a `top_k` outside 1 to 20 are rejected before the database or the model is touched (`None` stands in for both).
* 3 integration tests use the real PostgreSQL with a fake embedding service and three hand-made unit vectors: A (same direction as the query, similarity 1.0), B (45 degrees away, similarity 0.7071) and C (orthogonal, similarity 0.0). They check the ranking, the full provenance round trip (document ID, file name, pages, heading including `None`), `top_k`, and that the question is stripped before embedding.
* 8 unit tests for the endpoint use a fake retrieval service: response fields, the default `top_k`, trimming, and six invalid bodies that must return `422` with the standard error shape and never reach the service.

**Why:**

* Hand-made vectors give a known ranking without loading the model, so the test checks the SQL, not the model.
* The real Technical Report stays in the database during the tests. The integration test only asserts that A and B come first, which a real chunk cannot beat against a one-axis query vector, and its fixture deletes only its own document (10.8).
* The real model is checked manually through the running API (13.9).

**Rule found in Phase 5:** the `tests/` folders have no `__init__.py`, so pytest identifies a test module by its file name alone. Two files with the same name in `tests/unit/` and `tests/integration/` make collection fail with "import file mismatch". Every test file name must therefore be unique across all of `tests/`. The integration file is named `test_retrieval_integration.py` for this reason.

The suite has 93 tests at the end of Phase 5 (75 + 10 + 8).

---

## 13.9 Measured on the Real Model

**Observation:**
Through the running API, with the real EmbeddingGemma model on the stored Technical Report (31 chunks):

| Question | Top result | Similarity |
|---|---|---|
| How does Docling recognize the structure of tables? | Table Structure Recognition, pages 3-4 | 0.5499 |
| Which OCR engine can be used for scanned pages? | OCR, page 4 | 0.5792 |
| How many vacation days do employees get? (not answerable) | Performance table, page 5 | 0.0692 |

* All three numbers equal the Phase 4 throwaway check to four digits, so the service, the endpoint and the shared model reproduce what was measured by hand.
* Table question: the top three scores were 0.550, 0.545 and 0.531. The second hit (Applications) mentions table structure recognition in passing and the third (Abstract) is general, so the gap between a good and a weak match can be small. Whether the ranking among the top chunks is good enough is a Phase 7 question.
* OCR question: the References chunk ranked second (0.43). The bibliography noise seen in Phase 4 is confirmed.
* Unanswerable question: three chunks were still returned, all below 0.07.
* Still only three questions on one document: this is a smoke test, not evidence for a threshold.

---

# 14. Core Decision Rule

When considering a new technology, feature, or architectural change, ask:

```text
1. Does the product need it?
2. Is there a simpler solution?
3. Can we measure whether it helps?
4. Does it improve the system meaningfully?
5. Can we understand and maintain it?
```

If the answer is unclear, the default decision is to **keep the current solution and gather evidence first**.

---

## Final Principle

> Build the smallest coherent AI system that solves the problem, understand it deeply, evaluate it honestly, and add complexity only when the evidence justifies it.
