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
* The tested model produces **768-dimensional embeddings**.

The embedding model can be replaced later if evaluation shows that another model performs better.

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

---

## 4.2 Use HybridChunker

**Decision:**
Docling's `HybridChunker` is used as the initial chunking strategy.

**Why:**

* Provides a practical starting point for structured document chunking.
* Works with the structured representation produced by Docling.
* Avoids designing a custom chunking algorithm prematurely.

Chunking strategy can be changed later based on retrieval evaluation.

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

The `CREATE EXTENSION vector` migration is deferred to Phase 4, when pgvector is first needed.

---

## 10.3 Document Model Choices

**Decision:**
The `documents` table uses a UUID primary key generated in Python, a unique `storage_key`, and a `status` column stored as a plain string (`uploaded`, `processing`, `processed`, `failed`) rather than a PostgreSQL ENUM. No columns are added before a phase needs them.

**Why:**

* The upload code needs the document ID before the insert, to build the storage key.
* UUIDs cannot be guessed from the URL, unlike sequential integers.
* ENUM types are awkward to change in migrations; the application enforces the allowed values.
* Phase 3 will show which extra fields (for example an error message or page count) are really needed.

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

---

# 11. Core Decision Rule

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
