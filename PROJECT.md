# Enterprise AI Document Intelligence Platform

## Project Definition

**Enterprise AI Document Intelligence Platform** is an AI-powered internal knowledge assistant for companies.

The platform allows employees to ask natural-language questions about company documents and receive answers grounded in those documents, with citations pointing to the relevant document and page.

The project is designed as a realistic AI engineering system rather than a simple chatbot or a collection of disconnected technologies.

---

## Primary Goal

Build a practical AI-powered document intelligence platform that demonstrates the ability to:

* ingest real-world PDF documents
* understand and process their structure
* create meaningful document chunks
* generate semantic embeddings
* store and retrieve document knowledge
* use Retrieval-Augmented Generation (RAG)
* generate grounded answers using Gemini
* provide document and page citations
* expose the system through an API
* provide a simple user interface
* run locally through Docker
* later deploy the same application to AWS

The main objective is to learn and demonstrate **AI Engineering** through a complete, working system.

---

## Problem Being Solved

Companies often have large collections of internal documents such as:

* policies
* procedures
* technical documentation
* manuals
* reports
* guidelines
* internal knowledge documents

Employees may waste time searching through these documents to find specific information.

This platform provides a natural-language interface where an employee can ask a question instead of manually searching through documents.

Example:

```text
Employee:
"What is the procedure for handling an incident?"

System:
1. Searches relevant company documents.
2. Retrieves the most relevant sections.
3. Sends the retrieved context to Gemini.
4. Generates an answer grounded in that context.
5. Shows the source document and page.
```

The system should prefer saying that the information is not found rather than confidently generating unsupported information.

---

## Core User Flow

### Document ingestion

```text
PDF
 ↓
Document extraction
 ↓
Cleaning
 ↓
Structured chunking
 ↓
Embedding generation
 ↓
Vector storage
```

### Question answering

```text
User question
 ↓
Query embedding
 ↓
Vector similarity search
 ↓
Relevant chunks
 ↓
Context construction
 ↓
Gemini
 ↓
Grounded answer
 ↓
Source/page citations
```

---

## V1 Scope

V1 focuses on one strong end-to-end workflow:

> **Upload documents → process documents → retrieve relevant knowledge → answer questions with citations.**

### Included

* PDF document upload
* Object storage
* PDF/document parsing with Docling
* structured chunking with HybridChunker
* useful document/chunk metadata
* EmbeddingGemma embeddings
* PostgreSQL
* pgvector
* semantic vector retrieval
* Gemini API
* RAG
* source/page citations
* FastAPI backend
* simple Streamlit interface
* Docker-based local environment
* Airflow orchestration
* automated tests
* basic evaluation of retrieval and answer quality

### Not part of V1

The following should not be added unless a real requirement appears:

* custom model training
* fine-tuning
* local LLM serving
* multi-agent systems
* autonomous agents
* microservices
* Kubernetes
* Kafka
* complex authentication systems
* elaborate frontend development
* complex event-driven architecture
* unnecessary AWS services
* advanced ML models unrelated to the core product

Future ideas may be documented separately, but they should not complicate V1.

---

## Core Technology Stack

### AI

* Gemini API — answer generation
* EmbeddingGemma — document and query embeddings
* RAG — grounding answers in company documents

### Document Processing

* Docling — document/PDF understanding and extraction
* HybridChunker — structure-aware chunking

### Backend

* Python
* FastAPI
* Pydantic

### Data

* PostgreSQL
* pgvector

### Storage

Local:

* MinIO

AWS:

* Amazon S3

### Orchestration

* Apache Airflow

Airflow is responsible for orchestrating the document-processing workflow.

The actual processing logic must remain independent Python code.

### Infrastructure

Local:

* Docker
* Docker Compose

AWS:

* EC2
* RDS PostgreSQL
* S3
* IAM
* CloudWatch

Infrastructure as Code:

* Terraform

### Interface

* Streamlit

The interface should remain intentionally simple. The project is primarily an AI/backend engineering project, not a frontend project.

---

## Architecture Philosophy

The application uses a **modular monolith**.

The goal is to keep the system simple enough for one developer to understand while maintaining clear internal boundaries.

Conceptually:

```text
                    USER
                      │
                      ▼
                Streamlit UI
                      │
                      ▼
                 FastAPI API
                      │
          ┌───────────┼───────────┐
          │           │           │
          ▼           ▼           ▼
       Storage      Database      AI
          │           │           │
          ▼           ▼           ▼
        S3/MinIO   PostgreSQL   Gemini
                    + pgvector
```

The internal application is divided by responsibility rather than deployed as separate services.

---

## Repository Structure

The project should follow clear boundaries:

```text
app/
├── api/
├── core/
├── db/
├── services/
├── pipeline/
└── schemas/
```

### `app/api/`

Contains FastAPI routes and HTTP-level concerns.

Examples:

* document endpoints
* question/ask endpoint
* health endpoint

### `app/services/`

Contains application services and integrations.

Examples:

* storage service
* embedding service
* LLM service
* retrieval service
* RAG service

### `app/pipeline/`

Contains the document-processing logic.

The pipeline should remain independent from FastAPI and Airflow.

Example:

```text
extract
   ↓
clean
   ↓
chunk
   ↓
embed
   ↓
store
```

### `app/db/`

Contains:

* database models
* database session management
* repositories
* database-related logic

### `app/schemas/`

Contains Pydantic models used for API requests and responses.

---

## Document Processing

The document-processing pipeline uses:

```text
PDF
 ↓
Docling
 ↓
Structured document representation
 ↓
HybridChunker
 ↓
Chunks + useful metadata
 ↓
EmbeddingGemma
 ↓
768-dimensional vectors
 ↓
PostgreSQL + pgvector
```

The system should preserve useful provenance information alongside each chunk.

Conceptually:

```text
Chunk
├── text
├── document_id
├── page_number
├── section / heading
├── useful document metadata
└── embedding
```

The exact metadata schema should be based on the information actually available from the document-processing libraries rather than inventing unnecessary fields.

---

## RAG System

The initial RAG implementation uses dense vector retrieval.

```text
Question
 ↓
EmbeddingGemma
 ↓
Query vector
 ↓
pgvector similarity search
 ↓
Top relevant chunks
 ↓
Context
 ↓
Gemini
 ↓
Answer + citations
```

The initial system should prioritize correctness, simplicity, and explainability.

More advanced retrieval techniques such as:

* hybrid keyword/vector retrieval
* reranking
* query expansion

should only be introduced if evaluation demonstrates that the initial retrieval approach is insufficient.

---

## Airflow

Airflow is used as an orchestration layer for document processing.

It does **not** contain the core processing logic.

Conceptually:

```text
Airflow
   │
   ├── extract task
   ├── clean task
   ├── chunk task
   ├── embed task
   └── store task
```

The underlying Python functions remain independently executable.

This allows development and testing without requiring Airflow to be running.

The architectural principle is:

> **Pipeline logic should not depend on the orchestration system.**

Airflow manages workflow execution; Python code performs the actual work.

---

## Local Environment

The initial development environment runs locally using Docker Compose.

Target local infrastructure:

```text
Docker Compose
│
├── FastAPI
├── Streamlit
├── PostgreSQL + pgvector
├── MinIO
└── Airflow
```

MinIO provides an S3-compatible object-storage interface during local development.

This allows the application to use an S3-style storage abstraction before moving to AWS.

---

## AWS Deployment

The application should later be deployed to AWS without redesigning the application.

Target mapping:

```text
Local                     AWS
────────────────────────────────────
MinIO                 →   S3
PostgreSQL + pgvector →   RDS PostgreSQL
FastAPI               →   EC2
Streamlit             →   EC2
Docker                →   Docker
Environment config    →   AWS configuration
```

Supporting services:

```text
IAM
CloudWatch
Terraform
```

AWS is treated as the deployment environment rather than the product itself.

The project should avoid adding AWS services simply to increase the number of technologies used.

---

## Portability Principle

The application should be built so that the core application logic does not depend on a specific environment.

For example:

```text
Local:
Storage → MinIO

AWS:
Storage → S3
```

The application should interact with a storage abstraction rather than spreading MinIO- or S3-specific logic throughout the codebase.

The same principle applies to configuration and database connectivity.

The goal is:

> **Build the application correctly once, containerize it, and deploy the same application to AWS with environment-specific configuration.**

---

## Evaluation

The project must not rely only on whether the application appears to work.

The RAG system should eventually have a small evaluation dataset containing:

```text
Question
Expected information
Expected source/page
```

Evaluation should help determine:

* whether retrieval finds the correct chunks
* whether the answer is grounded in retrieved context
* whether citations point to the correct source
* where the system fails

Advanced retrieval techniques should be introduced only when evaluation provides a reason to use them.

---

## Engineering Constraints

The project should follow these constraints:

1. AI Engineering is the center of the system.
2. Every technology must have a clear purpose.
3. Avoid overengineering.
4. Prefer simple production-oriented solutions.
5. Keep processing logic independently testable.
6. Preserve document provenance.
7. Evaluate before adding advanced retrieval techniques.
8. Keep local development practical on the available hardware.
9. Keep the application portable between local infrastructure and AWS.
10. Do not add technologies only for CV keywords.
11. Prefer understanding a smaller system deeply over building a larger system superficially.

---

## Definition of Done

V1 is considered complete when a user can:

1. Start the system locally.
2. Upload a PDF.
3. Store the document.
4. Process the document through the ingestion pipeline.
5. Generate embeddings.
6. Store chunks and embeddings in PostgreSQL/pgvector.
7. Ask a natural-language question.
8. Retrieve relevant document chunks.
9. Generate a grounded answer through Gemini.
10. See the source document and page citation.
11. Run the application through Docker.
12. Run the main tests successfully.
13. Evaluate the basic RAG quality using a small evaluation dataset.
14. Understand and explain the major architectural and technology decisions.

The project is not considered complete merely because the code runs.

The owner should be able to explain:

* why each major technology was chosen
* how the document pipeline works
* how embeddings work
* how vector retrieval works
* how RAG works
* how citations are produced
* why Airflow is separated from pipeline logic
* how local infrastructure maps to AWS
* what the system's limitations are
* how the system could be improved
