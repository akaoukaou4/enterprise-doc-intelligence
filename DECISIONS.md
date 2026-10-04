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

# 9. Core Decision Rule

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
