# ROADMAP

**Question this file answers:** what are we building, in what order, and where are we now?
**Not here:** how the system works today (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff (read this first)

Updated: 2026-10-21, after Phase 8 (tag `phase-8`).

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Current phase:** Phase 8 is complete. **Phase 9 (Streamlit UI) is next and not started.**
- **What works today:** upload (`POST /api/v1/documents`) now leads to ingestion by itself. Airflow, started from the `airflow/` folder, checks every minute for `uploaded` documents, ingests them one at a time with `IngestionService`, and sets `documents.status` (`uploaded`, `processing`, `processed`, `failed`). Also: ingestion by hand (`scripts/ingest_document.py`, `scripts/ingest_folder.py`, both set the status too), retrieval (`POST /api/v1/search`), RAG answers (`POST /api/v1/ask`, default `top_k` 8), and the evaluation runner (`scripts/evaluate.py`). Last verified: 212 tests pass, Ruff clean (`scripts/check.ps1`).
- **What does not exist yet:** UI, Docker image for the app, AWS, Terraform. No list or delete endpoint for documents. No column for the failure reason (it is only in the Airflow task log).
- **Airflow in daily use:** the root `docker compose up -d` starts only PostgreSQL and MinIO. Airflow has its own compose: `cd airflow; docker compose up -d`, UI at http://localhost:8080 (login `airflow` / `airflow`). The DAG `ingest_documents` is created paused: unpause it once, and pause it when you stop working. Details: README.
- **Data state:** the 14 corpus PDFs in `data/corpus/` are all `processed` in the local database (302 chunks). Alembic head `8c1d5e7a2b96` (sets old ingested documents to `processed`). Evaluation set: `data/eval/questions.json` (version 5, 52 questions). Kept runs: `data/eval/results/`. Numbers: DECISIONS E-4 (evaluation) and E-5 (Airflow).
- **LLM:** `gemini-3.5-flash-lite` on the Gemini API free tier. Limits: `docs/provider_limits.md`. Data-use terms: DECISIONS D-36.
- **Rules in force:**
  - Only fictional or openly licensed documents may go to Gemini (free tier may use the data). The ISO 27001 PDF stays local.
  - No similarity threshold (D-33, E-4), hybrid search, reranking or vector index: Phase 7 showed no need.
  - Any change to chunking, embeddings, the prompt or `top_k`: rerun `scripts/evaluate.py` and compare with `data/eval/results/`. One change per experiment.
  - The AI never writes citations; code builds them from stored chunks.
  - Airflow only schedules and runs; ingestion and status logic stay in `app/` (D-45). The Airflow container reads `app/` and `scripts/` from the repository (read-only mount): a code change needs no rebuild, a change of `pyproject.toml` or `uv.lock` needs `docker compose build` in `airflow/`.
  - Resources: the Docker VM has 8 GB. One ingestion peaks at about 5.2 GB (E-5): close heavy apps while it runs.
- **Next action (Phase 9, step 1):** the 30-minute radar on Streamlit (current stable version, how to run it locally and call the FastAPI backend), then design the screens: upload, status, ask, answer with sources. Decide whether a list-documents endpoint is needed.
- **Open questions:** does the UI need a list endpoint, and a failure reason for `failed` documents (a `documents.error` column)? Decide in Phase 9, step 1.
- **Checks:** run `scripts/check.ps1` before every push. The pre-push hook runs it too.
- **Opening line for the new chat:** `Continue from the ROADMAP handoff.`
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
| 8 | Airflow | done | ingestion starts by itself after upload; same logic directly and through Airflow |
| 9 | Streamlit UI | **next** | full use without calling the API by hand |
| 10 | Complete local system | planned | everything works together locally |
| 11 | Containerization | planned | clean environment starts with Docker |
| 12 | AWS deployment | planned | core workflow works remotely |
| 13 | Terraform | planned | infrastructure recreated from code |
| 14 | Production quality | planned | logging, monitoring, reliability, improvements justified by evaluation |
| 15 | Portfolio | planned | repo understandable by a stranger |

Completed phases are not re-described here. For what each one built, read ARCHITECTURE. For why, read DECISIONS. Git tags mark the end of phases (`phase-N`).

**Milestones reached:** 1 backend foundation (end of Phase 2), 2 AI knowledge pipeline (Phase 4), 3 working AI assistant (Phase 6), 4 evaluated system (Phase 7), 5 automated ingestion (Phase 8).
**Milestones ahead:** 6 complete local product (Phase 10), 7 cloud deployment (Phase 13).

---

## Phase 8: Airflow (done)

**Goal:** ingestion starts by itself after upload and runs through Airflow with the same `IngestionService` logic; `documents.status` always tells the truth.

**Built:** a separate Airflow stack in `airflow/` (own compose, custom image, DAG `ingest_documents`); the status lifecycle in app code (`app/services/document_status.py`, `scripts/claim_documents.py`), used by Airflow and by both ingestion scripts; a migration that marks already ingested documents `processed`; tests for the status logic and the DAG helpers. Reasons: DECISIONS D-43 to D-46. Numbers: E-5. How to run it: README, "Airflow".

**Result in one line:** a PDF uploaded through the API became `processed` by itself in 3 min 51 s, produced the same chunks as the direct run (11 of 11 equal texts and pages, vector distance 0.000000), a corrupt PDF ended `failed`, and a worker killed in the middle recovered by itself.

**Known limits** (accepted, in the backlog): the failure reason is only in the Airflow log; a document that kills the worker is reset and retried at every run; the reset of stuck documents assumes no manual ingestion runs at the same time; up to 60 s pass between upload and the start of ingestion (polling).

**Exit conditions met:** (1) Airflow starts from its own compose and the UI opens; (2) upload to `processed` within 5 minutes with no manual script; (3) a corrupt PDF ends `failed` and is not claimed again; (4) direct and Airflow ingestion give the same chunks; (5) unit tests for the status logic and the DAG helpers, the DAG imports without errors in the container (`airflow dags list-import-errors`), `scripts/check.ps1` passes (212 tests), CI green at the tag.

---

## Phase 9: Streamlit UI

**Goal:** upload, see processing status, ask, read the answer and its sources. Simple on purpose; not a frontend project.

- Upload now starts ingestion by itself (Phase 8), so the UI only needs to show the status: `uploaded`, `processing`, `processed`, `failed`. `GET /api/v1/documents/{id}` already returns it.

**Exit:** the full workflow without calling the API by hand. May need a list-documents endpoint and a failure reason (decide then).

## Phase 10: Complete local system

**Goal:** Streamlit, FastAPI, MinIO, PostgreSQL + pgvector, Gemini and Airflow working together locally. Verify upload, processing, retrieval, RAG, citations, UI, Airflow and tests end to end.

## Phase 11: Containerization

**Goal:** a clean environment starts the whole system with Docker.

- The image is large (Docling, CPU PyTorch, sentence-transformers). Models need a persistent volume or a build step. Phase 8 already built such an image for Airflow (`airflow/Dockerfile`: the app in its own virtual environment from `uv.lock`); reuse that approach. There the code is mounted, not baked: an app image must bake it.
- `HF_TOKEN` and `GEMINI_API_KEY` are secrets passed at runtime, never baked into an image or committed.
- First request loads the embedding model lazily (about 22 s, mostly update checks to huggingface.co). In containers run offline with a pre-downloaded model; decide then between preloading at startup and lazy loading.

## Phase 12: AWS deployment

**Goal:** the same architecture on AWS: EC2 (API, UI), RDS PostgreSQL with pgvector, S3, IAM, CloudWatch. Gemini stays external.

- Map local to cloud, do not redesign: MinIO to S3, PostgreSQL to RDS, Docker to EC2.
- The same Alembic migrations run on RDS; the pgvector version depends on the RDS engine version, so check it.
- Size the instance for EmbeddingGemma (about 1.2 GB of weights) plus Docling. One ingestion peaked at about 5.2 GB in the Airflow container (E-5).
- Decide then whether the free Gemini tier is acceptable or a paid key is needed, and estimate cost first.
- Decide how Airflow runs there (same compose on EC2 is the baseline; managed Airflow is a cost question).

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
- Failure reason: stored only in the Airflow task log. If the UI must show it, add a `documents.error` column (Phase 9 decides).
- Models in the Airflow image: the embedding model is in the `hf-cache` volume, but the RapidOCR models (about 100 s of download) live in the container layer and are fetched again when the container is recreated. Check Docling's documented way to pre-download them first. Natural place: Phase 11.
- Ingestion edge cases: a document that kills the worker is reset and retried at every run (no attempt counter); the reset of stuck documents assumes no manual ingestion runs at the same time.
- Cold start: the first run of an ingestion task took about 66 s before the work started, a retry only 9 s (E-5). Disk cache on the HDD is the suspected cause, not proven. Measure again on an SSD or on AWS before tuning anything.
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
