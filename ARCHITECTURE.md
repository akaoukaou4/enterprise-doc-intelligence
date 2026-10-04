# Architecture

## 1. Architectural Style

The project uses a **modular monolith** architecture.

The application is deployed as a small number of containers, while the Python application itself is organized into clear internal modules.

The goal is to maintain:

* clear separation of responsibilities
* simple local development
* independent testing
* easy debugging
* low operational complexity
* portability to AWS

The project does **not** use microservices.

The architecture should remain simple until the application has a real reason to become more complex.

---

## 2. High-Level Architecture

```text
                         USER
                           │
                           ▼
                    Streamlit UI
                           │
                           ▼
                     FastAPI API
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       Document          RAG / AI        Application
       Services          Services          Services
          │                │
          │                ├──────────────► Gemini API
          │                │
          │                └──────────────► EmbeddingGemma
          │
          ├──────────────► Object Storage
          │                MinIO / S3
          │
          └──────────────► PostgreSQL
                           + pgvector
```

The main application is responsible for coordinating these components.

---

## 3. Repository Architecture

Target structure:

```text
enterprise-doc-intelligence/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── services/
│   ├── pipeline/
│   └── schemas/
│
├── airflow/
│   └── dags/
│
├── ui/
│
├── migrations/
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── data/
│   ├── sample_docs/
│   └── eval/
│
├── scripts/
│
├── docker/
│
├── docs/
│
├── .env.example
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── PROJECT.md
├── ROADMAP.md
└── README.md
```

Each directory should have a clear responsibility.

New directories should only be introduced when a real requirement appears.

### Implemented so far (end of Phase 1)

```text
app/
├── main.py            # create_app() application factory
├── api/
│   ├── deps.py        # shared FastAPI dependencies (DbSession, services)
│   ├── health.py      # /health, /health/db
│   └── v1/
│       ├── router.py  # /api/v1 router
│       └── info.py    # /api/v1/info (example route → service)
├── core/
│   ├── config.py      # typed settings (pydantic-settings)
│   ├── logging.py     # centralized logging setup
│   └── errors.py      # exceptions and error handlers
├── db/
│   └── session.py     # SQLAlchemy engine, session factory, get_db
├── services/
│   └── info.py        # example application service
└── schemas/
    ├── health.py
    ├── errors.py
    └── info.py
```

`app/pipeline/` is not created yet. It arrives in Phase 3.

---

# 4. Application Layers

The application is organized into several logical layers.

```text
API
 │
 ▼
Application Services
 │
 ├── Document Services
 ├── Retrieval Services
 ├── RAG Services
 └── Storage / AI Integrations
 │
 ▼
Infrastructure
 │
 ├── PostgreSQL
 ├── pgvector
 ├── MinIO / S3
 ├── Gemini API
 └── EmbeddingGemma
```

The exact implementation can evolve, but responsibilities should remain separated.

---

## 5. API Layer

Location:

```text
app/api/
```

The API layer contains FastAPI routes.

Example responsibilities:

```text
POST /documents
GET  /documents/{id}
POST /ask
GET  /health
```

The API layer should primarily handle:

* HTTP requests
* request validation
* authentication later if required
* calling application services
* formatting responses
* HTTP-level errors

Business logic should not be placed directly inside route functions.

For example:

```text
Bad:

FastAPI route
 ├── parse PDF
 ├── chunk document
 ├── generate embeddings
 ├── write database
 └── call Gemini
```

Instead:

```text
FastAPI route
      │
      ▼
Application service
      │
      ▼
Pipeline / AI / database services
```

This keeps the system easier to test and maintain.

### Current endpoints

```text
GET /health          liveness: the process is up
GET /health/db       readiness: the database is reachable
GET /api/v1/info     example route → service (app name, version, environment)
```

### Conventions

* **Versioning:** business endpoints live under `/api/v1`. Operational endpoints (`/health`, `/health/db`) stay at the root so infrastructure checks do not change with API versions.
* **Dependency injection:** services and database sessions are provided to routes through FastAPI dependencies defined in `app/api/deps.py`. Routes receive a ready-to-use service and call it.
* **Errors:** every error response has one shape: `{"error": {"code": "...", "message": "..."}}`. Services raise `AppError` subclasses (`NotFoundError`, `ValidationFailedError`, `ExternalServiceError`) and the registered handlers convert them to HTTP responses. FastAPI's own errors (unknown URL, invalid input) use the same shape. Unexpected exceptions return a generic message and are logged in full on the server, so internals are never leaked to clients.

---

# 6. Document Processing Architecture

The document pipeline is responsible for converting a PDF into searchable knowledge.

```text
                         PDF
                          │
                          ▼
                       Docling
                          │
                          ▼
              Structured document data
                          │
                          ▼
                    HybridChunker
                          │
                          ▼
                  Document chunks
                          │
                          ▼
                  EmbeddingGemma
                          │
                          ▼
                   Vector embeddings
                          │
                          ▼
                  PostgreSQL + pgvector
```

The pipeline should preserve useful document provenance.

A chunk should conceptually contain:

```text
Chunk
├── id
├── document_id
├── text
├── page_number
├── section / heading
├── useful metadata
└── embedding
```

The exact schema should be based on the actual information available from Docling and the application requirements.

---

# 7. Document Storage

Original documents are stored separately from their processed representations.

```text
Original PDF
     │
     ▼
Object Storage
     │
     ├── Local → MinIO
     │
     └── AWS   → S3
```

PostgreSQL stores metadata about the document.

Conceptually:

```text
Document
├── id
├── filename
├── storage_key
├── content_type
├── created_at
└── processing status
```

The database should not be used to store the original PDF binary unless there is a concrete reason to do so.

---

# 8. Database Architecture

The primary database is:

**PostgreSQL + pgvector**

PostgreSQL stores both application data and vector embeddings.

Conceptually:

```text
PostgreSQL
│
├── documents
│
├── document_chunks
│     ├── text
│     ├── metadata
│     └── embedding
│
└── other application data
```

pgvector provides vector similarity search.

The initial retrieval strategy uses dense vector similarity.

The system should avoid introducing a separate vector database unless PostgreSQL/pgvector becomes insufficient for a demonstrated requirement.

### Connection handling

The SQLAlchemy engine is created lazily in `app/db/session.py` with `pool_pre_ping` enabled, so the app starts without a database and recovers by itself after the database restarts. Routes get one session per request through the `get_db` dependency, and the session is always closed afterwards. `DATABASE_URL` is optional in the settings so tests and CI can run without a database.

---

# 9. Embedding Architecture

Embedding generation is handled through a dedicated embedding service.

```text
Document chunk
      │
      ▼
EmbeddingGemma
      │
      ▼
768-dimensional vector
      │
      ▼
PostgreSQL + pgvector
```

The same embedding model must be used consistently for:

* document chunks
* user queries

Conceptually:

```text
Document
   ↓
EmbeddingGemma
   ↓
Vector A


Question
   ↓
EmbeddingGemma
   ↓
Vector B
```

The vectors can then be compared through pgvector similarity search.

---

# 10. Retrieval Architecture

The initial retrieval system is intentionally simple.

```text
User question
      │
      ▼
EmbeddingGemma
      │
      ▼
Query vector
      │
      ▼
pgvector similarity search
      │
      ▼
Top-K chunks
      │
      ▼
Context builder
```

The retrieved chunks should retain their metadata so that the system can later construct accurate citations.

Initial retrieval is dense semantic retrieval.

More advanced approaches such as:

* hybrid retrieval
* BM25
* reranking
* query expansion

should only be added when evaluation demonstrates a need for them.

---

# 11. RAG Architecture

The RAG service combines retrieval and generation.

```text
                       User question
                              │
                              ▼
                       Query embedding
                              │
                              ▼
                       Vector retrieval
                              │
                              ▼
                       Relevant chunks
                              │
                              ▼
                       Context builder
                              │
                              ▼
                  ┌─────────────────────┐
                  │ Question + Context  │
                  └──────────┬──────────┘
                             │
                             ▼
                          Gemini
                             │
                             ▼
                      Grounded answer
                             │
                             ▼
                   Answer + citations
```

The LLM should receive retrieved document context rather than being expected to know the company's internal information independently.

The RAG service is responsible for:

* receiving the question
* retrieving relevant chunks
* constructing context
* calling Gemini
* processing the response
* returning the answer and citation information

---

# 12. Citation Architecture

Citations are based on metadata preserved during document processing.

Conceptually:

```text
Retrieved chunk
│
├── document_id
├── page_number
├── section
└── text
```

The final answer can therefore reference:

```text
Source:
Document: Employee Handbook.pdf
Page: 14
```

The exact citation format can evolve with the UI.

The important architectural requirement is:

> **Retrieval must preserve enough provenance information to identify where the answer came from.**

---

# 13. Airflow Architecture

Airflow is an orchestration layer, not the document-processing implementation.

```text
                         Airflow
                            │
                            ▼
                     Document DAG
                            │
             ┌──────────────┼──────────────┐
             ▼              ▼              ▼
          Extract         Clean          Chunk
             │              │              │
             └──────────────┼──────────────┘
                            ▼
                         Embed
                            │
                            ▼
                          Store
```

The actual processing functions live in:

```text
app/pipeline/
```

Airflow tasks call these functions.

This creates a separation:

```text
Pipeline
= What work is performed

Airflow
= When/how the work is orchestrated
```

The pipeline must remain executable without Airflow.

This is important for:

* local development
* unit testing
* debugging
* future orchestration changes

---

# 14. Development Execution Modes

The system should support two conceptual execution modes.

### Direct development mode

Used for fast development and testing.

```text
FastAPI
   │
   ▼
Python pipeline
   │
   ▼
Database / Storage
```

### Orchestrated mode

Used when testing the production-style workflow.

```text
FastAPI
   │
   ▼
Airflow
   │
   ▼
Python pipeline
   │
   ▼
Database / Storage
```

This prevents Airflow from becoming a requirement for every development action.

---

# 15. Storage Abstraction

The application should use a storage abstraction rather than directly coupling business logic to MinIO.

Conceptually:

```text
Application
     │
     ▼
Storage interface
     │
     ├───────────────┐
     ▼               ▼
   MinIO             S3
   Local             AWS
```

The application should be able to switch between them through configuration.

The goal is not to build an elaborate abstraction framework.

A small, practical storage service is sufficient.

---

# 16. Local Deployment Architecture

Local development uses Docker Compose.

```text
Docker Compose
│
├── FastAPI
│
├── Streamlit
│
├── PostgreSQL
│    └── pgvector
│
├── MinIO
│
└── Airflow
```

External dependency:

```text
Gemini API
```

EmbeddingGemma may run locally for embedding generation.

The exact containerization strategy for the embedding component can be decided during implementation based on resource usage and development practicality.

Currently, Docker Compose runs PostgreSQL + pgvector and MinIO. The API runs on the host with `uvicorn`. Containerizing the application comes in Phase 11.

---

# 17. AWS Deployment Architecture

The target AWS architecture is intentionally simple.

```text
                         Users
                           │
                           ▼
                         EC2
                    ┌──────┴──────┐
                    │             │
                 FastAPI       Streamlit
                    │
          ┌─────────┴──────────┐
          ▼                    ▼
        RDS                   S3
    PostgreSQL             Documents
    + pgvector
          │
          ▼
      Vector search

External:
    Gemini API
```

Supporting AWS services:

```text
IAM
CloudWatch
Terraform
```

The initial deployment should avoid unnecessary AWS services.

---

# 18. Environment Separation

The same application should operate in different environments through configuration.

Example:

```text
Development
────────────────────────────
DATABASE_URL → local PostgreSQL
STORAGE      → MinIO
GEMINI       → Gemini API


AWS
────────────────────────────
DATABASE_URL → RDS
STORAGE      → S3
GEMINI       → Gemini API
```

Environment-specific values should not be hardcoded into application logic.

Secrets and configuration should be supplied through environment variables or appropriate deployment configuration.

In code, all configuration is read through one typed `Settings` object (`app/core/config.py`) loaded from environment variables and `.env`. Settings are added only when a phase needs them.

---

# 19. Testing Architecture

Testing is divided into two main levels.

```text
tests/
├── unit/
└── integration/
```

### Unit tests

Test individual pieces of logic independently.

Examples:

* chunk processing
* metadata extraction
* context construction
* retrieval logic
* citation formatting

Unit tests replace dependencies (for example `get_db`) with fakes using FastAPI's `dependency_overrides`, so they run fast, need no database, and work in CI.

### Integration tests

Test interactions between components.

Examples:

* PostgreSQL + pgvector
* object storage
* document ingestion
* retrieval pipeline
* API endpoints

Integration tests need real services and are added from Phase 2 onward.

The test strategy should remain proportional to the project's size.

---

# 20. Architecture Evolution

The architecture should evolve based on demonstrated requirements.

Initial system:

```text
Modular monolith
+
PostgreSQL/pgvector
+
MinIO
+
Airflow
+
Gemini
```

Possible future evolution:

```text
Dense retrieval
      ↓
Evaluation
      ↓
Hybrid retrieval if needed
      ↓
Reranking if needed
      ↓
Other improvements if justified
```

The same principle applies to infrastructure.

A new technology should be introduced only when:

1. the current architecture has a demonstrated limitation,
2. the new technology solves that limitation,
3. the additional complexity is justified.

---

# 21. Core Architectural Principles

### Separation of responsibilities

Each component should have one clear primary responsibility.

### Pipeline independence

Document-processing logic must not depend on FastAPI or Airflow.

### Provenance preservation

Document metadata must survive the ingestion and retrieval process so citations remain possible.

### Infrastructure portability

Application logic should not be tightly coupled to MinIO, S3, or a particular deployment environment.

### Simple first

The first implementation should use the simplest architecture that can satisfy the requirements.

### Evaluation before optimization

Retrieval and RAG improvements should be driven by measured failures rather than assumptions.

### One application, multiple environments

The core application should remain the same between local development and AWS deployment.

---

## 22. Architectural Mental Model

The entire system can be understood as five major layers:

```text
┌─────────────────────────────────────┐
│              USER / UI              │
│             Streamlit              │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│                API                  │
│              FastAPI                │
└──────────────────┬──────────────────┘
                   │
┌──────────────────▼──────────────────┐
│          APPLICATION LOGIC          │
│  Documents | Retrieval | RAG | AI  │
└───────────┬─────────────┬───────────┘
            │             │
┌───────────▼───────┐ ┌───▼───────────┐
│    DATA LAYER     │ │   AI LAYER    │
│ PostgreSQL        │ │ Gemini         │
│ pgvector          │ │ EmbeddingGemma │
│ MinIO / S3        │ │                │
└───────────────────┘ └────────────────┘

          ORCHESTRATION
              Airflow
                 │
                 ▼
        Document Processing
```

The architecture should remain understandable from this diagram.

If the system becomes significantly more complicated than this without a strong reason, the complexity should be questioned before implementation.
