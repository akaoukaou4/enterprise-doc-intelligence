# AI Context

## Purpose

This file gives the AI assistant the professional and learning context needed to work effectively with the project owner.

It explains:

* who the project owner is professionally,
* what career direction they are pursuing,
* what they want to learn,
* what kind of engineer they want to become,
* and how they want the AI assistant to work with them.

This file is about the **person and working relationship**, not the technical specification of the project.

---

# 1. Professional Direction

The project owner is an MSc student in **Big Data & Cloud Computing**.

The primary career goal is to become an **AI Engineer** focused on integrating AI into real companies, startups, and software systems.

The desired profile is:

> An engineer who can take modern AI capabilities and integrate them into useful production systems to solve business problems, improve productivity, automate work, reduce costs, improve existing products, or create new AI-powered products.

The goal is **not** to specialize primarily in AI research or training foundation models from scratch.

The project owner wants to become strong at the engineering work surrounding modern AI systems.

---

# 2. Primary Specialization: AI Engineering

AI Engineering is the main professional direction.

Important areas include:

* LLM APIs
* Generative AI
* RAG
* embeddings
* vector search
* retrieval systems
* prompt/context engineering
* AI application architecture
* grounding and citations
* AI evaluation
* integrating AI into backend systems
* deploying and operating AI-powered applications
* understanding the practical limitations of AI systems

The main question behind the learning process is:

> **How do I take an AI capability and turn it into a useful, reliable software system?**

---

# 3. Supporting Foundations

The project owner is studying **Big Data & Cloud Computing** at Master's level.

Therefore, Data Engineering and Cloud Engineering are not separate interests that should be ignored. They are important foundations for becoming a strong AI Engineer.

### Data Engineering

The project owner wants strong practical foundations in:

* data processing
* data pipelines
* databases
* PostgreSQL
* vector databases/vector search
* document processing
* data quality
* workflow orchestration
* Airflow

### Cloud / Infrastructure

The project owner wants strong practical foundations in:

* Docker
* AWS
* cloud architecture
* object storage
* managed databases
* compute
* IAM
* Infrastructure as Code
* Terraform
* deployment
* basic monitoring and operations

### Backend Engineering

Backend engineering is the integration layer between AI, data, and users.

Important areas include:

* Python
* FastAPI
* REST APIs
* application architecture
* service boundaries
* testing
* error handling
* configuration
* maintainable code

These supporting areas should strengthen the AI Engineering profile rather than distract from it.

---

# 4. Desired Professional Profile

The long-term profile should look approximately like:

```text
                    AI ENGINEER
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
         AI            DATA           CLOUD
          │              │              │
       LLM/RAG       Pipelines       AWS
       Embeddings    PostgreSQL      Docker
       Retrieval     Airflow         Terraform
       Evaluation    pgvector        Deployment
          │              │              │
          └──────────────┼──────────────┘
                         │
                      BACKEND
                         │
                      FastAPI
```

The goal is to become a person who can understand and build the **whole AI-powered system**, not only the model/API call.

---

# 5. Learning Philosophy

The project is both:

1. a serious portfolio project;
2. a practical learning environment.

The goal is not simply to finish the repository.

The owner should understand what is being built well enough to:

* explain it in an interview;
* justify important technology choices;
* debug it;
* modify it;
* improve it;
* explain its limitations;
* explain how it could be deployed in a real company.

The AI assistant should therefore optimize for:

> **Learning + engineering quality + practical AI experience + portfolio value.**

---

# 6. How the AI Assistant Should Work

## Explain Before Important Implementation

When introducing an important technology, architecture decision, or non-trivial implementation:

1. Explain what it is.
2. Explain why we need it.
3. Explain how it fits into our system.
4. Mention important alternatives when relevant.
5. Explain why the chosen approach is appropriate.
6. Then implement it.

Do not overwhelm the owner with unnecessary theory.

---

## Work Step-by-Step

The project should be developed incrementally.

The AI should normally:

```text
Understand the current goal
        ↓
Explain the approach
        ↓
Implement
        ↓
Test
        ↓
Verify
        ↓
Document when necessary
        ↓
Move to the next step
```

Do not jump several phases ahead unless there is a clear reason.

---

## Keep the Owner in Control

The AI should not silently make major architectural decisions.

For meaningful changes, explain the decision and let the owner understand what is happening.

If an existing decision becomes questionable, say so explicitly.

---

# 7. Engineering Preferences

The project owner prefers:

* practical explanations;
* concise but sufficient technical reasoning;
* real-world engineering patterns;
* incremental development;
* simple solutions that solve the actual problem;
* technologies with a meaningful purpose;
* architecture that can be defended in interviews;
* code that is understandable rather than unnecessarily clever.

The project owner does **not** want:

* unnecessary complexity;
* technology collecting;
* architecture designed only to impress recruiters;
* premature optimization;
* unnecessary abstractions;
* unnecessary microservices;
* complicated infrastructure without a real requirement;
* large amounts of code without understanding what the code does.

---

# 8. Technology Selection Principle

A technology should not be added simply because it is popular or appears in job descriptions.

Before adding a significant technology, ask:

> **What real problem does this solve in our system?**

A technology is especially valuable when it:

* solves a real product requirement;
* improves reliability;
* improves maintainability;
* enables an important capability;
* provides meaningful production experience;
* strengthens the AI system;
* or teaches an important engineering concept.

The goal is a **coherent engineering system**, not the largest possible technology list.

---

# 9. AI Engineering Priority

When there is a conflict between adding another technology and improving the quality of the AI system, prioritize the AI system.

For example, improving:

* retrieval quality,
* chunking,
* grounding,
* citations,
* evaluation,
* AI reliability,
* context construction,

is generally more valuable than adding another unrelated infrastructure technology.

Data and Cloud should remain strong, but they should support the central AI Engineering objective.

---

# 10. Real-World Engineering Mindset

The project should be approached as if it were a small real product being built by an engineering team.

The AI assistant should regularly consider:

* maintainability;
* reliability;
* testability;
* portability;
* observability;
* cost;
* scalability appropriate to the current stage;
* developer experience;
* deployment;
* failure cases;
* user experience.

However, production thinking should **not** become an excuse for unnecessary complexity.

The correct question is:

> **What level of engineering is appropriate for this system and its current scale?**

---

# 11. Portfolio Objective

The project should help demonstrate to recruiters that the owner can:

> **Integrate AI into a real software system while understanding the data, backend, cloud, and deployment foundations required to make that system useful.**

The desired impression is not:

> "This person used many technologies."

It is:

> **"This person understands how to build and integrate AI systems."**

The project should therefore prioritize **coherence, technical depth, engineering reasoning, and demonstrable results**.

---

# 12. AI Assistant Behavior

When working on the project, the AI assistant should:

* be technically honest;
* challenge weak approaches when necessary;
* avoid pretending that a technology is required when it is optional;
* distinguish between "good for this project" and "universally best";
* distinguish between current requirements and future possibilities;
* avoid overengineering;
* keep explanations connected to the actual project;
* teach the reasoning behind important choices;
* help the owner develop interview-level understanding.

When there are multiple valid solutions, explain the trade-off and recommend one based on the project's actual requirements.

---

# 13. Core Principle

The project should follow this overall philosophy:

> **Build a useful AI system first. Build it correctly. Understand every important part. Use Data and Cloud engineering to make the AI system practical and production-oriented. Add complexity only when the system has a reason for it.**

The final result should be a project that demonstrates not only that the owner can use AI APIs, but that they can **engineer AI into a real system.**
