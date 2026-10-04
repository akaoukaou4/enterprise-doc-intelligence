# Engineering Principles

This document defines the engineering rules that guide the development of the Enterprise AI Document Intelligence Platform.

The goal is to build a system that is technically credible, understandable, maintainable, and useful without introducing complexity that does not serve the product.

---

## 1. AI Engineering Is the Primary Focus

The project is primarily an **AI Engineering project**.

The main learning and engineering focus is:

* LLM integration
* RAG
* embeddings
* retrieval
* document processing
* grounding
* citations
* evaluation
* integrating AI into a usable application

Data Engineering, Cloud, DevOps, and Backend Engineering are important supporting foundations.

They should strengthen the AI system rather than distract from it.

---

## 2. Every Technology Needs a Reason

A technology should never be added simply because:

* it is popular
* it looks good on a CV
* another project uses it
* it is considered "production-grade"
* it is interesting to learn

Before adding a technology, answer:

> **What real problem in this project does it solve?**

If there is no clear answer, it should probably not be added.

Examples:

```text
PostgreSQL
→ application data + vector storage

pgvector
→ semantic vector retrieval

Airflow
→ document pipeline orchestration

Docker
→ reproducible application environment

AWS
→ real cloud deployment

Terraform
→ reproducible infrastructure
```

---

## 3. Prefer Simple Production-Oriented Engineering

The goal is not to build the most sophisticated architecture possible.

The goal is to build the simplest architecture that is:

* correct
* understandable
* testable
* maintainable
* deployable
* extensible

Complexity must be justified by a real requirement.

A simple working solution is preferred over a sophisticated unfinished solution.

---

## 4. Learn While Building

The project is both:

1. a portfolio project
2. a learning environment

When implementing something important, the reasoning should be understood rather than copied blindly.

For major technologies and decisions, the owner should understand:

* what the technology does
* why it is being used
* what problem it solves
* how it interacts with the rest of the system
* its limitations
* reasonable alternatives

The objective is not just to make the code work.

The objective is to become capable of explaining and modifying the system independently.

---

## 5. Build the Smallest Useful Version First

The first implementation should solve the core problem end-to-end.

The preferred progression is:

```text
Simple working system
        ↓
Test it
        ↓
Evaluate it
        ↓
Find real limitations
        ↓
Improve it
```

Not:

```text
Design everything
        ↓
Add every advanced technology
        ↓
Spend weeks building infrastructure
        ↓
Eventually try to make the product work
```

---

## 6. Separate Application Logic From Infrastructure

Application logic should not be tightly coupled to infrastructure.

For example:

```text
Application
     │
     ▼
Storage abstraction
     │
 ┌───┴───┐
 ▼       ▼
MinIO   S3
```

Similarly:

```text
Pipeline logic
      │
      ▼
Airflow
```

rather than putting the actual document-processing logic inside Airflow-specific code.

This makes the application easier to:

* test
* debug
* run locally
* deploy
* change later

---

## 7. Keep the Document Pipeline Independently Testable

The document pipeline is an important part of the AI system.

Its processing functions should be executable without:

* FastAPI
* Streamlit
* Airflow
* the full application

Conceptually:

```text
PDF
 ↓
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

Each stage should be understandable and testable independently where practical.

Airflow orchestrates these stages but should not own their implementation.

---

## 8. Preserve Provenance

Document processing must preserve enough information to identify where retrieved knowledge came from.

Whenever possible, useful metadata should travel with the chunk.

For example:

```text
Chunk
├── document_id
├── page_number
├── section
├── text
└── embedding
```

This is important because the system is not only expected to answer questions.

It should also explain **where the information came from**.

Therefore:

> Provenance is part of the data model, not an afterthought added at the UI layer.

---

## 9. Use Existing AI Models Intelligently

The project should focus on **integrating AI effectively**, not unnecessarily training models from scratch.

For V1:

* Gemini handles generation.
* EmbeddingGemma handles embeddings.
* RAG provides grounding.
* The application provides the engineering around these models.

Custom training, fine-tuning, or custom model development should only be introduced if a demonstrated requirement makes them worthwhile.

---

## 10. Treat RAG as an Engineering System

RAG is not simply:

```text
Vector database + LLM
```

The system should be treated as a pipeline:

```text
Document processing
        ↓
Chunking
        ↓
Embedding
        ↓
Indexing
        ↓
Query embedding
        ↓
Retrieval
        ↓
Context construction
        ↓
Generation
        ↓
Citation
        ↓
Evaluation
```

Each stage can affect the final answer.

When something goes wrong, investigate the appropriate stage instead of immediately changing the LLM.

---

## 11. Evaluate Before Optimizing

Do not add advanced RAG techniques based only on assumptions.

Start with:

```text
Dense retrieval
      ↓
Evaluation
      ↓
Identify failure
      ↓
Choose improvement
```

For example, if evaluation shows that semantic retrieval misses exact policy numbers or technical identifiers, then hybrid retrieval may become justified.

If retrieval is already good, adding more retrieval systems only increases complexity.

---

## 12. Prefer Measurable Improvements

When possible, improvements should be supported by evidence.

Instead of:

> "This should make RAG better."

Prefer:

> "The evaluation dataset shows that the current retriever misses these questions, so we are testing another retrieval strategy."

The project should gradually develop a small evaluation dataset that allows changes to be compared.

---

## 13. Keep Boundaries Clear

Each module should have a clear responsibility.

For example:

```text
app/api/
→ HTTP/API concerns

app/services/
→ application and integration services

app/pipeline/
→ document processing

app/db/
→ database concerns

app/schemas/
→ data validation and API models
```

Avoid putting unrelated logic into whichever file happens to be convenient.

---

## 14. Avoid Premature Abstraction

Do not create abstractions simply because they might be useful someday.

First understand the actual requirement.

For example, a small storage service may be enough:

```text
storage.upload()
storage.download()
storage.delete()
```

There is no need to build a large plugin architecture for storage providers unless the project actually requires it.

The rule is:

> Abstract real variation, not imaginary future variation.

---

## 15. Avoid Premature Infrastructure

Do not introduce infrastructure complexity before the application needs it.

The preferred progression is:

```text
Application
   ↓
Local integration
   ↓
Docker
   ↓
AWS deployment
   ↓
Infrastructure as Code
```

Do not introduce Kubernetes, microservices, queues, distributed systems, or additional AWS services without a concrete reason.

---

## 16. Cloud Should Be Meaningful

Cloud technologies should represent real engineering responsibilities.

For this project:

```text
EC2
→ application runtime

RDS
→ managed PostgreSQL

S3
→ document storage

IAM
→ AWS permissions

CloudWatch
→ basic monitoring/logging

Terraform
→ infrastructure reproducibility
```

Cloud should not be used merely as a collection of services to mention on a CV.

---

## 17. Build Once, Deploy Portably

The application should be designed so that the same core application can run locally and on AWS.

Conceptually:

```text
                 SAME APPLICATION
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
          Local                   AWS
             │                     │
          MinIO                   S3
          PostgreSQL              RDS
          Docker                 Docker
```

Environment-specific configuration should determine infrastructure connections.

The application should not require a separate architecture just because it moves to AWS.

---

## 18. Test at the Appropriate Level

Not everything requires a large integration test.

Use the simplest test that provides useful confidence.

```text
Pure logic
→ unit test

Component interaction
→ integration test

API behavior
→ API/integration test

Full system behavior
→ selected end-to-end tests
```

Tests should provide confidence without becoming a second project.

---

## 19. Debug the Root Cause

When something fails, identify which layer is responsible.

Example:

```text
Bad answer
    │
    ├── Retrieval problem?
    │
    ├── Chunking problem?
    │
    ├── Context construction problem?
    │
    ├── Prompt problem?
    │
    └── LLM generation problem?
```

Do not immediately change multiple components at once.

Make one meaningful change at a time whenever practical.

This makes debugging and learning much easier.

---

## 20. Keep Development Fast

The project should remain practical for the available development environment.

Development should not require starting every component for every small task.

For example:

```text
Writing/testing chunking
→ run the pipeline directly

Testing database logic
→ run PostgreSQL

Testing full orchestration
→ start Airflow

Testing complete application
→ start the full environment
```

The development workflow should minimize unnecessary waiting and resource usage.

---

## 21. Security Is Engineering Hygiene, Not the Product Theme

Security should be handled responsibly as normal engineering practice.

Examples:

* never commit API keys
* use environment variables for secrets
* keep `.env` out of Git
* avoid exposing unnecessary services
* validate inputs
* use appropriate permissions

However, security is not the central product theme of this project.

The project should remain focused on:

> AI-powered enterprise document intelligence.

---

## 22. Don't Build Future Features Too Early

Future ideas should not automatically become current implementation requirements.

Examples of possible future features:

* hybrid retrieval
* reranking
* advanced evaluation
* authentication
* multi-user support
* document versioning
* advanced monitoring
* more sophisticated cloud infrastructure

These should be added only when the core system is working and there is a clear reason.

A documented future idea is enough.

It does not need to exist in the codebase.

---

## 23. Prefer Coherence Over Technology Count

A strong portfolio project does not need to contain every modern technology.

The technologies should form a coherent system:

```text
Docling
   ↓
HybridChunker
   ↓
EmbeddingGemma
   ↓
pgvector
   ↓
RAG
   ↓
Gemini
   ↓
FastAPI
   ↓
Streamlit
```

Supported by:

```text
PostgreSQL
MinIO / S3
Airflow
Docker
AWS
Terraform
```

Each component should have a clear relationship with the product.

---

## 24. Explain Important Decisions

For important technical choices, the reasoning should be documented.

Examples:

* Why PostgreSQL + pgvector?
* Why EmbeddingGemma?
* Why Docling?
* Why HybridChunker?
* Why Gemini?
* Why Airflow?
* Why MinIO locally?
* Why EC2 + RDS + S3?
* Why modular monolith?
* Why dense retrieval initially?

These decisions belong in `DECISIONS.md`.

The goal is not to document every small implementation detail.

Document decisions that affect architecture, technology selection, or future development.

---

## 25. Change Decisions When Evidence Changes

These principles are guidelines, not permanent laws.

If implementation or evaluation provides strong evidence that an existing approach is insufficient, the architecture can change.

The correct process is:

```text
Current approach
      ↓
Evidence / limitation
      ↓
Investigate alternatives
      ↓
Compare trade-offs
      ↓
Make decision
      ↓
Update documentation
```

Changing a decision is not failure.

Keeping a bad decision simply because it was written down is worse.

---

## 26. Optimize for Understanding

The project should remain understandable to its owner.

At every stage, the owner should be able to answer:

* What does this component do?
* Why does it exist?
* What data enters it?
* What data leaves it?
* What can fail?
* How do I test it?
* How would I change it?

If a component cannot be explained clearly, it should be investigated before adding more complexity around it.

---

## 27. Portfolio Quality Comes From Engineering Quality

The project should not be optimized only for appearance on GitHub.

A strong portfolio project should demonstrate:

* a real problem
* a coherent architecture
* meaningful AI integration
* good engineering practices
* testing
* evaluation
* reproducibility
* deployment
* clear technical reasoning

The final project should be something the owner can confidently discuss in an interview from both the **AI** and **engineering** perspectives.

---

## 28. Core Rule

When uncertain about a technical decision, use this order:

```text
1. Does the product need it?
          ↓
2. Is there a simpler solution?
          ↓
3. Can we test/evaluate the need?
          ↓
4. Does it improve the system meaningfully?
          ↓
5. Can we understand and maintain it?
```

If the answer to these questions is unclear, do not add the complexity yet.

> **Build a small, coherent, well-understood AI system first. Then make it better based on evidence.**
