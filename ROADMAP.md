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

**Next**

### Objective

Build the data foundation required by the application.

### Build

PostgreSQL:

* database connection
* SQLAlchemy setup
* migrations
* document model
* document metadata

Object storage:

* MinIO integration
* upload
* download
* delete
* storage abstraction

### Expected result

```text
PDF
 │
 ▼
MinIO

Document metadata
 │
 ▼
PostgreSQL
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

---

# Phase 3 — Document Processing Pipeline

### Objective

Turn uploaded PDFs into structured, meaningful chunks.

### Build

```text
PDF
 ↓
Docling
 ↓
Structured document
 ↓
Cleaning
 ↓
HybridChunker
 ↓
Chunks + metadata
```

### Preserve

Where useful:

* document ID
* page number
* section / heading
* chunk text
* other provenance metadata

### Learning focus

* document AI
* PDF processing
* document structure
* chunking strategies
* provenance

### Exit condition

A real PDF can be processed into useful chunks with page/source information preserved.

---

# Phase 4 — Embedding System

### Objective

Convert document chunks into semantic vectors.

### Build

* EmbeddingGemma integration
* embedding service
* document embedding generation
* query embedding generation
* pgvector storage
* vector dimension validation

Current embedding baseline:

```text
google/embeddinggemma-300m
→ 768 dimensions
```

### Expected result

```text
Chunk
 ↓
EmbeddingGemma
 ↓
768-dimensional vector
 ↓
pgvector
```

### Learning focus

* embeddings
* semantic representation
* document vs query embeddings
* vector databases
* similarity search concepts

### Exit condition

Document chunks and user queries can consistently be converted into compatible vectors.

---

# Phase 5 — Retrieval System

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

### Evaluate

At minimum:

* retrieval relevance
* correct source retrieval
* citation correctness
* answer grounding
* obvious hallucination cases

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

The DAG calls the existing Python pipeline functions.

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
* demo
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
