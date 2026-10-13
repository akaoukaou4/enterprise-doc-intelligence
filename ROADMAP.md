# ROADMAP

**Question this file answers:** what are we building, in what order, and where are we now?
**Not here:** how the system works today (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff (read this first)

Updated: 2026-10-13, after Phase 6.

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Current phase:** Phase 6 is complete. **Phase 7 (evaluation) is next and not started.**
- **What works today:** upload (`POST /api/v1/documents`), manual ingestion (`scripts/ingest_document.py <document_id>`), retrieval (`POST /api/v1/search`), RAG answers (`POST /api/v1/ask`). Last verified: 129 unit tests pass, 15 integration tests skip without Docker, Ruff clean, CI green (commit `2203c20`).
- **What does not exist yet:** evaluation, Airflow, UI, Docker image for the app, AWS, Terraform. No list or delete endpoint for documents. Upload does not start ingestion. `documents.status` stays `uploaded`.
- **Data state:** 3 policy PDFs of a fictional German company are ingested (21, 11, 32 chunks). 11 more policy PDFs exist outside the repo, not ingested. Everything private stays outside Git.
- **LLM:** `gemini-3.5-flash-lite` on the Gemini API free tier. Limits and data-use terms: DECISIONS.
- **Rules in force:**
  - Only fictional or openly licensed documents may go to Gemini (free tier may use the data). The ISO 27001 PDF stays local.
  - No similarity threshold, hybrid search, reranking or vector index until Phase 7 shows a need.
  - One change per experiment, measured against the same question set.
  - The AI never writes citations; code builds them from stored chunks.
- **Next action:** design the Phase 7 question set (see Phase 7).
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
| 7 | Evaluation | **next** | repeatable measurement of quality |
| 8 | Airflow | planned | same ingestion logic runs directly and through Airflow |
| 9 | Streamlit UI | planned | full use without calling the API by hand |
| 10 | Complete local system | planned | everything works together locally |
| 11 | Containerization | planned | clean environment starts with Docker |
| 12 | AWS deployment | planned | core workflow works remotely |
| 13 | Terraform | planned | infrastructure recreated from code |
| 14 | Production quality | planned | logging, monitoring, reliability, improvements justified by evaluation |
| 15 | Portfolio | planned | repo understandable by a stranger |

Completed phases are not re-described here. For what each one built, read ARCHITECTURE. For why, read DECISIONS. Git tags mark the end of phases (`phase-N`).

**Milestones reached:** 1 backend foundation (end of Phase 2), 2 AI knowledge pipeline (Phase 4), 3 working AI assistant (Phase 6).
**Milestones ahead:** 4 evaluated system (Phase 7), 5 complete local product (Phase 10), 6 cloud deployment (Phase 13).

---

## Phase 7: Evaluation (next)

**Goal:** know whether the system works, and make every later change prove itself against numbers. This comes before any optimization.

**Why now:** Phase 6 answers were checked by hand on a handful of questions. That is a demo, not a measurement. The open questions below cannot be answered without data.

**Build:**
1. **Corpus.** Ingest the 11 remaining policy PDFs in batches (a few minutes per file on this CPU). Only fictional or openly licensed documents.
2. **Question set** in `data/eval/` as JSON (not CSV: `.gitignore` ignores `data/**/*.csv`). Each item: question, expected answer facts, expected document, expected page, kind. Aim for about 40 questions to start, in these kinds:
   - answerable from one passage
   - answerable only by combining passages
   - topics that overlap across files (harassment, smoking, working hours, confidentiality), to test citation precision
   - **not answerable**, and near-misses on the same topic
   - table and heading cases (known Phase 3 limits)
   - cross-language (a French question against English documents worked once)
3. **Runner** `scripts/evaluate.py`: calls the services directly (not HTTP), writes one result file per run, paces requests under the free-tier limit.
4. **Metrics**, with retrieval and generation measured separately so a wrong answer can be traced:
   - retrieval: is the expected document and page in the top k?
   - citation: is each citation a chunk that supports the answer? how often is there padding (unneeded citations)?
   - refusal: answerable questions answered, unanswerable refused
   - answer correctness against the expected facts (reviewed by hand at first)
5. **Baseline** first. Then one experiment at a time; record each result next to the baseline.

**Experiments to run after the baseline exists (not before):**
- similarity threshold for "not found", chosen from logged scores, compared with the model's own `found` (data so far: separates on one corpus, fails on another)
- heading as embedding title versus none
- chunk size 256, 512, 1024 (`MAX_CHUNK_TOKENS`)
- `top_k` (default 5) and question length limit (1000): both are guesses
- merging heading-only chunks into the next chunk
- excluding or down-weighting bibliography chunks
- Docling `repeat_table_header` option
- `gemini-3.5-flash-lite` versus a larger Flash model, and the thinking level (small free quota on larger models)
- a vector index (only if search time becomes measurable)

**Rules:** no optimization on intuition. Pace requests (about 15 per minute, 500 per day on the free tier). Log numbers only.

**Exit condition:** a repeatable evaluation that says whether a change made the system better or worse.

---

## Phase 8: Airflow

**Goal:** orchestrate ingestion without moving logic into Airflow.

- DAG tasks call existing functions: `app/pipeline/`, `EmbeddingService`, `ChunkService`. `scripts/ingest_document.py` is the blueprint.
- Closes today's gap: upload does not start ingestion.
- Owns the `documents.status` lifecycle: `uploaded`, `processing`, `processed`, `failed`.
- Timing to plan for: about 10 s per page conversion, about 1.6 to 2.5 s per chunk embedding on this CPU; a short PDF takes about 3 minutes. Timeouts and retries must allow for it.
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

**Goal:** logging, error handling, configuration, tests, monitoring, reproducibility, deployment reliability. RAG improvements (hybrid retrieval, reranking, better chunking, prompt changes, filtering) only if Phase 7 evidence justifies them.

## Phase 15: Portfolio

**Goal:** README, architecture diagram, setup and deployment instructions, screenshots, a demo with fictional or openly licensed documents, evaluation results, key decisions, limitations, future work. The README tells the story: problem, solution, architecture, RAG pipeline, technology choices, evaluation, deployment, lessons learned.

---

## Backlog (small items, no phase yet)

- List and delete endpoints for documents (cleanup needed SQL and the MinIO console).
- Model loading lock (two simultaneous first requests may both load the model; harmless for one developer).
- Map `ValueError` from services to an HTTP error for callers that skip the schemas.
- Check accent display in PowerShell 5.1.

---

## Priority rules

1. Core AI functionality, 2. data pipeline, 3. backend integration, 4. evaluation, 5. orchestration, 6. UI, 7. containers, 8. cloud, 9. infrastructure as code, 10. advanced improvements.

If a later phase blocks understanding of an earlier one, go back. A phase is done when it works and I can explain it, not when the tool is installed.

## What must not happen

No AWS before the local system works. No Kubernetes, microservices, Kafka, agents, fine-tuning or separate vector database without a measured requirement. No hybrid retrieval without evaluation evidence. No elaborate frontend. No technology added for CV keywords.

> Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.
