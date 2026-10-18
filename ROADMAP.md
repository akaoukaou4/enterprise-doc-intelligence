# ROADMAP

**Question this file answers:** what are we building, in what order, and where are we now?
**Not here:** how the system works today (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff (read this first)

Updated: 2026-10-18, after Phase 7 (tag `phase-7`).

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Current phase:** Phase 7 is complete. **Phase 8 (Airflow) is next and not started.**
- **What works today:** upload (`POST /api/v1/documents`), ingestion by hand (`scripts/ingest_document.py <document_id>`) or for a whole folder (`scripts/ingest_folder.py`), retrieval (`POST /api/v1/search`), RAG answers (`POST /api/v1/ask`, default `top_k` 8), and the evaluation runner (`scripts/evaluate.py`). Last verified: 195 tests pass, Ruff clean, CI green (commit `fab0ec1`).
- **What does not exist yet:** Airflow, UI, Docker image for the app, AWS, Terraform. No list or delete endpoint for documents. Upload does not start ingestion. `documents.status` stays `uploaded`.
- **Data state:** the 14 corpus PDFs in `data/corpus/` are all ingested in the local database (302 chunks). Evaluation set: `data/eval/questions.json` (version 5, 52 questions). Kept runs: `data/eval/results/` (baseline and `top_k` 8). Scratch runs: `data/eval/runs/` (git-ignored). Numbers: DECISIONS E-4.
- **LLM:** `gemini-3.5-flash-lite` on the Gemini API free tier. Limits: `docs/provider_limits.md`. Data-use terms: DECISIONS D-36.
- **Rules in force:**
  - Only fictional or openly licensed documents may go to Gemini (free tier may use the data). The ISO 27001 PDF stays local.
  - No similarity threshold (D-33, E-4), hybrid search, reranking or vector index: Phase 7 showed no need.
  - Any change to chunking, embeddings, the prompt or `top_k`: rerun `scripts/evaluate.py` and compare with `data/eval/results/`. One change per experiment.
  - The AI never writes citations; code builds them from stored chunks.
- **Next action (Phase 8, step 1):** design the DAG. Tasks call the existing functions (`IngestionService` in `app/services/ingestion.py`; `scripts/ingest_folder.py` is the blueprint). Airflow owns the `documents.status` lifecycle.
- **Documents:** README (use), ROADMAP (this), ARCHITECTURE (system now), DECISIONS (why), PROJECT (scope). Working rules live in the private kit, loaded by the Project instructions.

---

## Status

| # | Phase | Status | Exit condition (short) |
|---|---|---|---|
| 0 | Foundation | done | environment, CI, Docker services reproducible |
| 1 | FastAPI foundation | done | API starts, health checks, errors, tests |
| 2 | Database and object storage | done | PDF stored in MinIO, metadata in PostgreSQL |
| 3 | Document processing | done | PDF becomes clean chunks with pages and headings |
| 4 | Embeddings | done | chunks and queries become compatible 768-dim vectors |
| 5 | Retrieval | done | a question retrieves the right chunks with provenance |
| 6 | Gemini + RAG | done | grounded answer with citations, or a clear refusal |
| 7 | Evaluation | done | repeatable measurement of quality |
| 8 | Airflow | **next** | same ingestion logic runs directly and through Airflow |
| 9 | Streamlit UI | planned | full use without calling the API by hand |
| 10 | Complete local system | planned | everything works together locally |
| 11 | Containerization | planned | clean environment starts with Docker |
| 12 | AWS deployment | planned | core workflow works remotely |
| 13 | Terraform | planned | infrastructure recreated from code |
| 14 | Production quality | planned | logging, monitoring, reliability, improvements justified by evaluation |
| 15 | Portfolio | planned | repo understandable by a stranger |

Completed phases are not re-described here. For what each one built, read ARCHITECTURE. For why, read DECISIONS. Git tags mark the end of phases (`phase-N`).

**Milestones reached:** 1 backend foundation (end of Phase 2), 2 AI knowledge pipeline (Phase 4), 3 working AI assistant (Phase 6), 4 evaluated system (Phase 7).
**Milestones ahead:** 5 complete local product (Phase 10), 6 cloud deployment (Phase 13).

---

## Phase 7: Evaluation (done)

**Goal:** know whether the system works, and make every later change prove itself against numbers.

**Built:** bulk ingestion (`scripts/ingest_folder.py`, `app/services/ingestion.py`), the 52-question set (`data/eval/questions.json`), the runner and scoring (`scripts/evaluate.py`, `app/evaluation/`), a baseline and one experiment (`top_k` 8). Numbers and reasons: DECISIONS D-41, D-42, E-4. How to run it: README, "Evaluate".

**Result in one line:** retrieval puts the expected source in the top 3 for every answerable question; the one real failure at `top_k` 5 (q07) is fixed at 8; the default is now 8.

**Not tested** (no measured need; do them only if a change in the corpus or the requirements justifies it): similarity threshold (measured: does not separate, E-4), heading as embedding title, chunk size 256 or 1024, merging heading-only chunks, excluding bibliography chunks, Docling `repeat_table_header`, a larger Flash model or thinking level (20 requests a day on the free tier), a vector index.

**Exit condition met:** a repeatable evaluation that says whether a change made the system better or worse.

---

## Phase 8: Airflow

**Goal:** orchestrate ingestion without moving logic into Airflow.

- DAG tasks call existing functions: `IngestionService` (`app/services/ingestion.py`), which chains `app/pipeline/`, `EmbeddingService` and `ChunkService`. `scripts/ingest_folder.py` and `scripts/ingest_document.py` are the blueprints.
- Closes today's gap: upload does not start ingestion.
- Owns the `documents.status` lifecycle: `uploaded`, `processing`, `processed`, `failed`.
- Timing to plan for: about 10 s per page conversion, about 1.6 to 2.5 s per chunk embedding on this CPU; a short PDF takes about 3 minutes (the 11 remaining corpus files took about 18 minutes together). Timeouts and retries must allow for it.
- The worker needs the Hugging Face token (EmbeddingGemma is gated) or a pre-downloaded model volume.

**Exit:** the same logic works directly and through Airflow.

## Phase 9: Streamlit UI

**Goal:** upload, see processing status, ask, read the answer and its sources. Simple on purpose; not a frontend project.

**Exit:** the full workflow without calling the API by hand. May need a list-documents endpoint (decide then).

## Phase 10: Complete local system

**Goal:** Streamlit, FastAPI, MinIO, PostgreSQL + pgvector, Gemini and Airflow working together locally. Verify upload, processing, retrieval, RAG, citations, UI, Airflow and tests end to end.

## Phase 11: Containerization

**Goal:** a clean environment starts the whole system with Docker.

- The image is large (Docling, CPU PyTorch, sentence-transformers). Models need a persistent volume or a build step.
- `HF_TOKEN` and `GEMINI_API_KEY` are secrets passed at runtime, never baked into an image or committed.
- First request loads the embedding model lazily (about 22 s, mostly update checks to huggingface.co). In containers run offline with a pre-downloaded model; decide then between preloading at startup and lazy loading.

## Phase 12: AWS deployment

**Goal:** the same architecture on AWS: EC2 (API, UI), RDS PostgreSQL with pgvector, S3, IAM, CloudWatch. Gemini stays external.

- Map local to cloud, do not redesign: MinIO to S3, PostgreSQL to RDS, Docker to EC2.
- The same Alembic migrations run on RDS; the pgvector version depends on the RDS engine version, so check it.
- Size the instance for EmbeddingGemma (about 1.2 GB of weights) plus Docling.
- Decide then whether the free Gemini tier is acceptable or a paid key is needed, and estimate cost first.

**Exit:** the core workflow works remotely.

## Phase 13: Terraform

**Goal:** recreate the AWS infrastructure from code, after understanding it manually in Phase 12.

**Exit:** the infrastructure can be rebuilt from the configuration.

## Phase 14: Production quality

**Goal:** logging, error handling, configuration, tests, monitoring, reproducibility, deployment reliability. RAG improvements (hybrid retrieval, reranking, better chunking, prompt changes, filtering) only if evaluation evidence justifies them. Rerun `scripts/evaluate.py` against `data/eval/results/` before and after any such change.

## Phase 15: Portfolio

**Goal:** README, architecture diagram, setup and deployment instructions, screenshots, a demo with fictional or openly licensed documents, evaluation results, key decisions, limitations, future work. The README tells the story: problem, solution, architecture, RAG pipeline, technology choices, evaluation, deployment, lessons learned.

---

## Backlog (small items, no phase yet)

- List and delete endpoints for documents (cleanup needed SQL and the MinIO console).
- Model loading lock (two simultaneous first requests may both load the model; harmless for one developer).
- Map `ValueError` from services to an HTTP error for callers that skip the schemas.
- Check accent display in PowerShell 5.1.
- Evaluation gaps: source matching is page-level, so a chunk on the right page counts even if it lacks the fact; a qualified answer (q16, q24) is judged by hand because the refusal metric only reads `found`. Literal fact matching was tried and rejected (D-41).
- Typos in expected facts of `questions.json` (q02 "untilyou", q45 "givenas"); "10-2027" typo in `data/corpus/SOURCES.md`; the Dress Code and Handbook PDFs share the document id NS-HR-POL-005.

---

## Priority rules

1. Core AI functionality, 2. data pipeline, 3. backend integration, 4. evaluation, 5. orchestration, 6. UI, 7. containers, 8. cloud, 9. infrastructure as code, 10. advanced improvements.

If a later phase blocks understanding of an earlier one, go back. A phase is done when it works and I can explain it, not when the tool is installed.

## What must not happen

No AWS before the local system works. No Kubernetes, microservices, Kafka, agents, fine-tuning or separate vector database without a measured requirement. No hybrid retrieval without evaluation evidence. No elaborate frontend. No technology added for CV keywords.

> Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.
