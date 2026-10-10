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

### Implemented so far (end of Phase 5)

```text
app/
├── main.py            # create_app() application factory
├── api/
│   ├── deps.py        # shared FastAPI dependencies (DbSession, services, the shared
│   │                  #   EmbeddingService, RetrievalService)
│   ├── health.py      # /health, /health/db
│   └── v1/
│       ├── router.py  # /api/v1 router
│       ├── info.py    # /api/v1/info (example route → service)
│       ├── documents.py  # POST /documents, GET /documents/{id}
│       └── search.py  # POST /search (retrieval inspection endpoint)
├── core/
│   ├── config.py      # typed settings (pydantic-settings)
│   ├── logging.py     # centralized logging setup
│   └── errors.py      # exceptions and error handlers
├── db/
│   ├── base.py        # SQLAlchemy declarative Base
│   ├── models.py      # Document, DocumentChunk, EMBEDDING_DIMENSIONS
│   └── session.py     # SQLAlchemy engine, session factory, get_db
├── services/
│   ├── info.py        # example application service
│   ├── storage.py     # StorageService (boto3 → MinIO / S3)
│   ├── documents.py   # DocumentService (validate, store file, insert row)
│   ├── embeddings.py  # EmbeddingService (EmbeddingGemma: documents and queries)
│   ├── chunks.py      # ChunkService (store chunks + vectors in document_chunks)
│   └── retrieval.py   # RetrievalService, RetrievedChunk (embed question → pgvector search)
├── pipeline/          # document processing, independent of FastAPI, Airflow and the database
│   ├── models.py      # Chunk (text, page_numbers, heading)
│   ├── extract.py     # PDF → Docling document
│   ├── chunk.py       # Docling document → Chunk list (EmbeddingGemma tokenizer,
│   │                  #   table of contents dropped)
│   ├── clean.py       # cleaning rules (pure functions)
│   └── process.py     # process_pdf(): extract → chunk → clean
└── schemas/
    ├── health.py
    ├── errors.py
    ├── info.py
    ├── documents.py   # DocumentResponse
    └── search.py      # SearchRequest, SearchHit, SearchResponse

migrations/
├── env.py             # Alembic setup (URL comes from Settings)
├── script.py.mako
└── versions/          # migrations (excluded from Ruff)
    ├── b475fddcd445_create_documents_table.py
    └── 3f9a7c2d1e84_add_pgvector_and_document_chunks.py

alembic.ini

scripts/
├── storage_roundtrip.py   # manual upload/download/delete check against MinIO
├── explore_docling.py     # convert one PDF with Docling and print what it produced
├── run_pipeline.py        # run the real process_pdf() on one PDF end to end (no storing)
└── ingest_document.py     # MinIO → pipeline → embeddings → PostgreSQL for one document

tests/
├── unit/              # fakes, run everywhere including CI
└── integration/       # real PostgreSQL + MinIO, skipped when unavailable
```

Scripts that import from `app` are run as modules from the project root, for example `uv run python -m scripts.run_pipeline`.

Test file names must be unique across all of `tests/` (there are no `__init__.py` files, so pytest identifies a test module by its file name). For example, the retrieval tests are `tests/unit/test_retrieval_service.py` and `tests/integration/test_retrieval_integration.py`.

The upload endpoint does not call the pipeline yet. Today a document is ingested by running `scripts.ingest_document` (direct execution mode). Connecting upload to processing, and the status transitions, come with Airflow in Phase 8.

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
GET  /health                   liveness: the process is up
GET  /health/db                readiness: the database is reachable
GET  /api/v1/info              example route → service (app name, version, environment)
POST /api/v1/documents         upload a PDF: store the file, insert the row, return metadata (201)
GET  /api/v1/documents/{id}    read the metadata of one document
POST /api/v1/search            retrieve the most similar chunks for a question (inspection endpoint)
```

The search endpoint reaches the embedding service (through `RetrievalService`). No endpoint calls the pipeline or the chunk service yet. There is no question endpoint (`/ask`) yet; it arrives with RAG (Phase 6), next to `/search`, which stays.

### Document endpoints

```text
POST /api/v1/documents (multipart file)
        │
        ▼
Route: read the bytes, call the service
        │
        ▼
DocumentService.create
   ├── validate: application/pdf, %PDF- bytes, not empty, within MAX_UPLOAD_MB
   ├── StorageService.upload   → MinIO / S3
   └── insert Document row     → PostgreSQL
        (if the insert fails: roll back and delete the stored file)
```

The response is `DocumentResponse` (`id`, `filename`, `content_type`, `size_bytes`, `status`, `created_at`). `storage_key` is internal and is not returned.

### Search endpoint

```text
POST /api/v1/search  {"question": "...", "top_k": 5}
        │
        ▼
SearchRequest (Pydantic): strip whitespace, question 1-1000 characters, top_k 1-20
        │   (invalid input → 422 validation_failed, the service is never called)
        ▼
Route (plain def): call RetrievalService.search, convert each hit to SearchHit
        │
        ▼
SearchResponse {"results": [ {document_id, filename, page_numbers, heading, text, similarity}, ... ]}
```

It is an inspection endpoint: it shows what retrieval returns, so a bad answer can later be traced to retrieval or to generation. The route is a plain `def`, so FastAPI runs the blocking embedding work in a thread pool and the server stays responsive. An empty database returns an empty list, not an error.

### Conventions

* **Versioning:** business endpoints live under `/api/v1`. Operational endpoints (`/health`, `/health/db`) stay at the root so infrastructure checks do not change with API versions.
* **Dependency injection:** services and database sessions are provided to routes through FastAPI dependencies defined in `app/api/deps.py`. Routes receive a ready-to-use service and call it. Most services are built per request; the `EmbeddingService` is the exception: one instance is shared by the whole process (see section 9).
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

### Implemented

The chunks themselves are produced in `app/pipeline/` (Phase 3). Embedding and storing are application services (Phase 4), so the pipeline package stays free of the model, the database and the web framework:

```text
PDF file
   │
   ▼
extract_document        pipeline/extract.py   Docling converter (created once, cached)
   │
   ▼
chunk_document          pipeline/chunk.py     HybridChunker with the EmbeddingGemma
   │                                          tokenizer (512 tokens); drops table-of-
   │                                          contents chunks (label "document_index");
   │                                          keeps page numbers and the nearest heading
   ▼
clean_chunks            pipeline/clean.py     removes \x08 and \ufeff, removes the license
   │                                          watermark line, drops chunks left empty
   ▼
list[Chunk]             pipeline/models.py    Chunk(text, page_numbers, heading)
   │
   ▼
EmbeddingService        services/embeddings.py   "title: <heading> | text: <chunk>"
   │                                             → 768-dimensional vectors
   ▼
ChunkService            services/chunks.py       replace the document's rows in
                                                 document_chunks (one transaction)
```

`process_pdf(path)` in `process.py` runs the first three stages in order. It does no storage or database work and imports no FastAPI or Airflow code. `scripts/ingest_document.py` chains the whole path for one uploaded document (download from storage, `process_pdf`, `embed_documents`, `replace_chunks`); Airflow tasks will call the same functions.

The stages are small and separate so each can be tested alone. `clean.py` is pure (text in, text out). `chunk_document` accepts a chunker as an argument, so tests use fake chunks without loading any model. `EmbeddingService` accepts a model, and `ChunkService` takes a database session, so each is tested with fakes or a real database without the other.

### What the chunk contains

```text
Chunk (pipeline, in memory)
├── text            the chunk text
├── page_numbers    list of pages (a chunk can span pages, e.g. [2, 3])
└── heading         nearest section heading, or None
```

When stored, the row in `document_chunks` adds `document_id`, `chunk_index`, `embedding`, and timestamps (see section 8). The schema comes from what Docling actually provides; see DECISIONS.md section 11.

### Known behavior and limits

* Page headers and footers are in Docling's `FURNITURE` layer and are skipped by the chunker.
* Text inside pictures is almost never part of the chunks.
* Tables become chunks of `row, column = value` text; a table can be split across chunks, and its header row can be lost.
* Every heading is reported at level 1, so only the nearest heading is kept, and some headings are wrong or missing.
* Speed on CPU is about 10 s per page for conversion, plus about 1.6 s per chunk for embeddings. A 9-page PDF takes about 3.5 minutes end to end.
* With the EmbeddingGemma tokenizer the 512-token budget produces larger chunks than the Phase 3 tokenizer: 31 chunks (was 49) for the Technical Report and 58 (was 72) for ISO 27001.

Details and reasoning are in DECISIONS.md sections 11 and 12.

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

Files are stored under the key:

```text
documents/<document_id>/<original filename>
```

The UUID in the key prevents collisions between files with the same name. The bucket itself (`documents`) is created by the `minio-init` container in Docker Compose, not by the application.

PostgreSQL stores metadata about the document, in the `documents` table:

```text
Document
├── id              UUID, primary key, generated in Python
├── filename        original file name (last path component)
├── storage_key     unique key of the file in object storage
├── content_type    application/pdf
├── size_bytes      file size
├── status          uploaded → processing → processed | failed
└── created_at      set by the database
```

`status` is a plain string, not a PostgreSQL ENUM; the application enforces the allowed values. Nothing sets `processing`, `processed` or `failed` yet; that comes with orchestration in Phase 8.

The database should not be used to store the original PDF binary unless there is a concrete reason to do so.

---

# 8. Database Architecture

The primary database is:

**PostgreSQL + pgvector**

PostgreSQL stores both application data and vector embeddings.

```text
PostgreSQL
│
├── documents
│
├── document_chunks
│     ├── id             UUID, primary key
│     ├── document_id    foreign key → documents.id, ON DELETE CASCADE
│     ├── chunk_index    order of the chunk in the document
│     ├── text           the chunk text
│     ├── page_numbers   integer[] (a chunk can span pages)
│     ├── heading        nearest section heading, nullable
│     ├── embedding      vector(768), NOT NULL
│     └── created_at
│
│     UNIQUE (document_id, chunk_index)
│
└── alembic_version
```

Both tables exist (Phase 4). The `vector` extension (version 0.8.7 locally) is created by the migration `3f9a7c2d1e84`. Phase 5 added no migration: retrieval only reads these tables.

Design points:

* Deleting a document deletes its chunks (cascade), so no orphan chunks exist.
* The unique constraint prevents duplicate chunks when a document is processed twice; its index also serves "all chunks of a document".
* `vector(768)` and `NOT NULL` make the database reject missing or wrong-sized vectors.
* There is no vector index (HNSW or IVFFlat). With tens of chunks per document an exact scan is instant; an index is added only if search time becomes measurable.

pgvector provides vector similarity search. Retrieval uses cosine distance (`cosine_distance` in SQLAlchemy through the `pgvector` package); the vectors are normalized, so similarity is `1 - distance`.

The initial retrieval strategy uses dense vector similarity.

The system should avoid introducing a separate vector database unless PostgreSQL/pgvector becomes insufficient for a demonstrated requirement.

### Connection handling

The SQLAlchemy engine is created lazily in `app/db/session.py` with `pool_pre_ping` enabled, so the app starts without a database and recovers by itself after the database restarts. Routes get one session per request through the `get_db` dependency, and the session is always closed afterwards. `DATABASE_URL` is optional in the settings so tests and CI can run without a database.

### Schema changes

Schema changes are versioned Alembic migrations:

```text
SQLAlchemy models (app/db/models.py)
        │
        ▼
alembic revision --autogenerate   → migration script (read before applying)
        │                            (written by hand when autogenerate cannot
        │                             express it, e.g. CREATE EXTENSION)
        ▼
alembic upgrade head              → PostgreSQL
```

Models inherit from `Base` (`app/db/base.py`), which Alembic reads to know what the tables should look like. `migrations/env.py` takes the database URL from `Settings`, so `alembic.ini` holds no real credentials. The same migration history will run against RDS on AWS.

Current history:

```text
b475fddcd445  create documents table
      ↓
3f9a7c2d1e84  add pgvector extension and document_chunks table   (head)
```

---

# 9. Embedding Architecture

Embedding generation is handled through a dedicated embedding service (`app/services/embeddings.py`).

```text
Document chunk
      │
      ▼
"title: <heading or none> | text: <chunk text>"
      │
      ▼
EmbeddingGemma
      │
      ▼
768-dimensional vector (length 1)
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
EmbeddingGemma  (document format)
   ↓
Vector A


Question
   ↓
EmbeddingGemma  (query prompt: "task: search result | query: ...")
   ↓
Vector B
```

The vectors can then be compared through pgvector similarity search.

### How the service works

* `embed_documents(chunks)` returns one vector per chunk, in the same order. The text it embeds is built by `build_document_text` from our own `Chunk`, so the real heading fills the model's title slot. Without a heading the result equals the model's own document prompt.
* `embed_query(question)` uses the model's query encoder, so questions and documents follow the formats the model was trained on.
* The model loads on first use, on CPU, through `sentence-transformers`. Importing the module stays fast, and unit tests use a fake model.
* When the model loads, the service checks that its output size equals the database column size (768) and raises a clear error otherwise.

### One shared instance in the API

The model takes seconds to load and uses memory, so the API creates one `EmbeddingService` for the whole process, never one per request. In `app/api/deps.py`, `get_embedding_service` is decorated with `lru_cache`, and `RetrievalService` receives that instance through `EmbeddingServiceDep`. The model still loads lazily, so the first search pays the loading cost.

```text
first POST /api/v1/search  →  model loads (about 22 s measured, mostly update checks to Hugging Face)
later searches             →  same instance, model already in memory
```

Two simultaneous first requests could both load the model, because there is no lock; for one developer this only wastes time, and it is recorded in DECISIONS.md 13.3. Whether to preload the model at startup is revisited in Phase 11, when container health checks are designed.

### Configuration

The model is one setting, `EMBEDDING_MODEL_ID` (default `google/embeddinggemma-300m`). The chunker's tokenizer and the embedding service both read it, so chunk size is always measured by the model that embeds the chunk. Changing to a model with another vector size needs a new migration.

### Access

EmbeddingGemma is a gated Hugging Face model: accept the license and log in once (`uv run hf auth login`). The token is stored under `HF_HOME` (on D:), outside the repository. Deployments will need it as a secret (`HF_TOKEN`) or pre-downloaded models in a volume.

### Storing

`ChunkService.replace_chunks(document_id, chunks, vectors)` validates that the chunk and vector counts match and that every vector has 768 values, then deletes the document's old chunks and inserts the new ones in one transaction. A failure rolls back and leaves the old chunks in place.

Phase 4 measurements: about 1.6 s per chunk on the development CPU; vectors have norm 1.0000.

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

### Implemented (Phase 5)

`RetrievalService` (`app/services/retrieval.py`) takes a database session and an embedding service, and exposes `search(question, top_k)`:

```text
search(question, top_k)
   │
   ├── strip the question; reject empty, longer than 1000 characters, or top_k outside 1-20 (ValueError)
   │
   ├── EmbeddingService.embed_query(question)          → query vector (768, normalized)
   │
   ├── SQL:  SELECT document_chunks.*, documents.filename,
   │                cosine_distance(embedding, query_vector) AS distance
   │         FROM document_chunks JOIN documents ON documents.id = document_chunks.document_id
   │         ORDER BY distance, document_id, chunk_index        (stable order on ties)
   │         LIMIT top_k
   │
   └── list[RetrievedChunk]    similarity = 1 - distance
```

`RetrievedChunk` is a frozen dataclass:

```text
RetrievedChunk
├── document_id
├── filename          (joined from documents, so no second lookup)
├── page_numbers
├── heading           (may be None)
├── text
└── similarity
```

It is a plain object, not a database row: callers never see the ORM model or the raw vector. The limits (`DEFAULT_TOP_K = 5`, `MAX_TOP_K = 20`, `MAX_QUESTION_CHARS = 1000`) are constants in the service, and the API schemas import them, so they are defined once. The API checks them first and returns a 422; the service checks again and raises `ValueError`, which is not mapped to an HTTP error because the API cannot let a bad value through. The numbers are guesses and are Phase 7 experiments.

Phase 5 measurement through the API, with the real model on the Technical Report: tables 0.5499, OCR 0.5792, unanswerable question 0.0692, identical to the Phase 4 hand check.

Dense search always returns the nearest chunks, even when the document cannot answer the question (see DECISIONS.md 12.11). The service therefore returns the similarity of every hit, so a "not found" rule can be applied later without changing its shape. Deciding when to answer "not found" is not solved by retrieval alone; it is decided in Phases 6 and 7 with evaluation data. Not added on purpose: a similarity threshold, a document filter, a vector index, hybrid search, reranking, query expansion.

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

The first half of this flow exists since Phase 5: `RetrievalService` returns the relevant chunks with their provenance, and the API already holds one shared `EmbeddingService` (see section 9). The RAG service will call `RetrievalService` and add the context builder, the Gemini call and the citations (Phase 6). Gemini is the first external network call in the request path, so its failures become `ExternalServiceError` (502), and its API key is a secret in the settings, never in the repository.

---

# 12. Citation Architecture

Citations are based on metadata preserved during document processing and stored with each chunk.

Conceptually:

```text
Retrieved chunk
│
├── document_id
├── filename
├── page_numbers
├── heading
└── text
```

The final answer can therefore reference:

```text
Source:
Document: Employee Handbook.pdf
Pages: 14
Section: 5.2 Policy
```

Because a chunk can span pages, a citation can show a page range. Because some headings are wrong or missing (see section 6), the page number is the more reliable part of a citation, and the section label is a helpful hint.

Since Phase 5 every search result already carries all of these fields (`RetrievedChunk`), so building a citation needs no extra database lookup.

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
app/pipeline/        extract, chunk, clean
app/services/        EmbeddingService, ChunkService
```

Airflow tasks call these functions. `scripts/ingest_document.py` already chains them directly and is the blueprint for the DAG.

This creates a separation:

```text
Pipeline and services
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

Conversion takes about 10 s per page on CPU and embedding about 1.6 s per chunk, so task timeouts and retries must allow for several minutes per document. The Airflow worker also needs access to the gated embedding model (Hugging Face token or a pre-downloaded model volume). The `documents.status` transitions belong to this phase.

---

# 14. Development Execution Modes

The system should support two conceptual execution modes.

### Direct development mode

Used for fast development and testing.

```text
FastAPI or script
   │
   ▼
Python pipeline + services
   │
   ▼
Database / Storage
```

Today this mode is `uv run python -m scripts.ingest_document <document_id>`.

### Orchestrated mode

Used when testing the production-style workflow.

```text
FastAPI
   │
   ▼
Airflow
   │
   ▼
Python pipeline + services
   │
   ▼
Database / Storage
```

This prevents Airflow from becoming a requirement for every development action.

---

# 15. Storage Abstraction

The application uses a storage abstraction rather than directly coupling business logic to MinIO.

```text
Application
     │
     ▼
StorageService (app/services/storage.py)
     │
     ▼
boto3 (S3 API)
     │
     ├───────────────┐
     ▼               ▼
   MinIO             S3
   Local             AWS
```

`StorageService` has three methods: `upload`, `download`, `delete`. It is the only code that imports boto3. boto3 failures are mapped to `NotFoundError` (missing key) or `ExternalServiceError`, so routes never see boto3 exceptions.

Switching between MinIO and S3 is a configuration change:

```text
Local:  MINIO_ENDPOINT=http://localhost:9000 + MinIO keys
AWS:    MINIO_ENDPOINT not set → boto3 talks to real S3 (IAM role on EC2)
```

The goal is not to build an elaborate abstraction framework. A small, practical storage service is sufficient.

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

EmbeddingGemma runs locally, on CPU, inside the application process (not as a separate service).

Currently, Docker Compose runs PostgreSQL + pgvector (the `pgvector/pgvector:pg18` image) and MinIO, plus a one-time `minio-init` container that creates the `documents` bucket. The API, the pipeline and the embedding model run on the host. Containerizing the application comes in Phase 11.

### Local machine setup (Windows)

* The project lives on D:. The uv cache and the Hugging Face cache are on D: as well (`UV_CACHE_DIR` and `HF_HOME` point to `D:\Backup\School\Project\_caches\...`), outside the repository, so they are never committed and C: stays free. The Hugging Face login token is stored there too.
* PyTorch is the CPU-only build, installed from an explicit `pytorch-cpu` uv index declared in `pyproject.toml`.
* Docling, PyTorch and sentence-transformers make the application image large, and Docling and EmbeddingGemma download models at first use. Phase 11 must give those models a persistent volume or a build-time download, with the Hugging Face token as a secret. The embedding model also asks huggingface.co for updates on every load even when cached (about 15 requests, most of the 22 s first search), so containers should run offline with the model pre-downloaded.

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

The same Alembic migrations run on RDS; `CREATE EXTENSION vector` is supported on RDS PostgreSQL, but the pgvector version depends on the RDS engine version, so it must be checked. The EC2 instance must be sized for EmbeddingGemma (about 1.2 GB of weights) plus Docling.

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

In code, all configuration is read through one typed `Settings` object (`app/core/config.py`) loaded from environment variables and `.env`. Settings are added only when a phase needs them. Current settings: application (`APP_NAME`, `APP_ENV`, `DEBUG`, `LOG_LEVEL`), database (`DATABASE_URL`), object storage (`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`), uploads (`MAX_UPLOAD_MB`) and the embedding model (`EMBEDDING_MODEL_ID`, which has a default and normally needs no `.env` entry). Phase 5 added no setting: the search limits are constants in `app/services/retrieval.py`, not environment values, because they are tuned with evaluation data and are not environment-specific. The Hugging Face token is not a setting: it is stored by `hf auth login` under `HF_HOME`, or supplied as `HF_TOKEN` in deployments.

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

Unit tests replace dependencies (for example `get_db`, the storage client, the embedding model, or the whole document service) with fakes, so they run fast, need no database, MinIO or model, and work in CI.

Pipeline tests follow the same rule: `test_pipeline_clean.py` (13 tests) uses the exact junk strings found in real PDFs, and `test_pipeline_chunk.py` (6 tests) uses a fake chunker, so no Docling model is loaded. `test_embedding_service.py` (6 tests) uses a fake model and checks the document format, the order of vectors, the query path, and the dimension check. `test_chunk_service.py` (2 tests) checks that bad input is rejected before anything is deleted. The real Docling conversion and the real embedding model are checked manually with `scripts/run_pipeline.py` and `scripts/ingest_document.py`, because they take minutes.

Phase 5 added two unit test files. `test_retrieval_service.py` (7 tests, parametrized) checks that an empty or too long question and a `top_k` outside 1-20 are rejected before the database or the model is touched. `test_search_api.py` (8 tests) replaces `get_retrieval_service` with a fake, and checks the response fields, the default `top_k`, trimming, and six invalid bodies that must return a 422 with the standard error shape and never reach the service.

### Integration tests

Test interactions between components.

Examples:

* PostgreSQL + pgvector
* object storage
* document ingestion
* retrieval pipeline
* API endpoints

Integration tests use the real PostgreSQL and MinIO containers. They skip themselves when `DATABASE_URL` or `MINIO_ENDPOINT` is not set, or when a service is not reachable, so CI (which has neither) stays green. Each test removes only the rows and files it created. The chunk integration tests (8) use small fake vectors of the right size, so they need no embedding model, and they cover provenance round trip, replacement, empty replacement, cascade deletion, rejected input, an unknown document, and a failed commit that must keep the old chunks.

The retrieval integration tests (3, in `test_retrieval_integration.py`) use a fake embedding service and three hand-made unit vectors with known similarity to the query: 1.0, 0.7071 and 0.0. They check the ranking, the provenance round trip (document ID, file name, pages, heading including `None`), `top_k`, and that the question is stripped before embedding. The real documents already in the database are left alone: the fixture creates and deletes only its own document, and the test asserts only that its two closest chunks come first.

Test file names must be unique across all of `tests/` (see section 3).

At the end of Phase 5 the suite has 93 tests.

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
