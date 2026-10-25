# ROADMAP

**Question this file answers:** what are we building, in what order, and where are we now?
**Not here:** how the system works today (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff (read this first)

Updated: 2026-10-26, Phase 11 done (tag `phase-11`, set after the docs commit). Phase 12 has not started.

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Current phase:** none running. Next is Phase 12 (AWS), starting with its radar, plan, exit conditions and exchange limit (WORKING_AGREEMENT section 5).
- **What works today:** the whole system runs in Docker with one command: `copy .env.example .env`, set `HF_TOKEN` and `GEMINI_API_KEY`, then `docker compose up -d --build`. One compose file starts PostgreSQL, MinIO, `migrate` (Alembic, once), `api` (EmbeddingGemma baked in), `ui`, and Airflow (scheduler, api-server, dag-processor, its own metadata database; code, DAG, Docling models and EmbeddingGemma baked in; the DAG is unpaused at creation). Features: upload, automatic ingestion with status, list, delete (409 while `processing`), search, ask with citations, the evaluation runner and the end-to-end check. Last verified 2026-10-25: `scripts/check.ps1` green (261 passed, none skipped), CI green on commit `c82f52e`, `scripts/e2e_check.py` passed all 11 checks against the containers (upload to `processed` 202 s).
- **What does not exist yet:** authentication (upload and delete are open; the Airflow UI uses the default login `airflow` / `airflow` and its port is published), AWS, Terraform, automated tests of the Streamlit screens, a failure-reason column, an image build in CI (the gated model needs a token that must not go into CI).
- **Run it:** README. For development outside Docker, start only the containers you need (`docker compose up -d postgres minio minio-init`) and run the API and UI on the host.
- **Data state:** the 14 corpus PDFs in `data/corpus/` are `processed` (302 chunks at the Phase 10 check; one document was re-ingested in Phase 11 and the count was not rechecked). Evaluation set: `data/eval/questions.json` (version 5, 52 questions). Kept runs: `data/eval/results/`. Numbers: DECISIONS E-4 (evaluation), E-5 (Airflow), E-6 (containers).
- **LLM:** `gemini-3.5-flash-lite` on the Gemini API free tier; no shutdown date announced when checked 2026-10-25. Limits: `docs/provider_limits.md`. Data-use terms: DECISIONS D-36.
- **Rules in force:**
  - Only fictional or openly licensed documents may go to Gemini (free tier may use the data), also in manual and e2e tests. The ISO 27001 PDF stays local. Never upload a personal file to test.
  - No similarity threshold (D-33), hybrid search, reranking or vector index: Phase 7 showed no need (E-4).
  - Any change to chunking, embeddings, the prompt or `top_k`: rerun `scripts/evaluate.py` and compare with `data/eval/results/`. One change per experiment.
  - The AI never writes citations; code builds them from stored chunks.
  - Airflow only schedules and runs; ingestion and status logic stay in `app/` (D-45). The code is baked into the images (D-53): after a change in `app/`, `scripts/`, `airflow/dags/`, `pyproject.toml` or `uv.lock`, run `docker compose up -d --build`.
  - The UI is an HTTP client of the API and imports nothing from `app/` (I15).
  - A Docker build checks the real imports in the stage where the system libraries exist, and includes the database driver. A check in another stage proves nothing.
  - Rerun `scripts/e2e_check.py` after any change to ingestion, the API or the deployment, and against each new environment (`API_URL`).
  - Docs are changed once, at the end of a phase. In the middle of a phase only a decision record, and only when code depends on it.
  - Resources: the Docker VM has 8 GB. All containers at idle use about 2.4 GB and one ingestion adds about 4.3 GiB (E-6): close heavy apps while it runs.
- **Next action:** Phase 12, step 0: compress the docs to budget (open question 3), then step 1: the 30-minute radar, then write the Phase 12 plan, exit conditions and limit here, before any code.
- **Open questions:** (1) E5 of Phase 11 (the stranger test: clone, set two tokens, `docker compose up -d --build`, follow the README) is **waived** by the owner and will be run on another PC. Until then the README is **unverified**. (2) Phase 12 decides authentication, the paid or free Gemini key, and how the gated model is built on AWS (see Phase 12). (3) The doc size budget is **waived** for Phase 11: step 0 of Phase 12 compresses ARCHITECTURE and DECISIONS and trims README and ROADMAP. (4) Docling's models sit in the default cache of the Airflow image user (uid 50000); with another `AIRFLOW_UID` (common on Linux) they may be missed: check this on the other PC.
- **Checks:** run `scripts/check.ps1` before every push (start the containers first, or the integration tests skip). The pre-push hook runs it too.
- **Opening line for the new chat:** `Continue from the ROADMAP handoff.`
- **Documents:** README (use), ROADMAP (this), ARCHITECTURE (system now), DECISIONS (why), PROJECT (scope), `airflow/README.md` (the Airflow image and DAG). Working rules live in the private kit, loaded by the Project instructions.

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
| 9 | Streamlit UI | done | full use without calling the API by hand |
| 10 | Complete local system | done | everything works together locally, checked by one script |
| 11 | Containerization | done (E5 and doc size waived) | the whole system starts with one Docker command |
| 12 | AWS deployment | planned | core workflow works remotely |
| 13 | Terraform | planned | infrastructure recreated from code |
| 14 | Production quality | planned | logging, monitoring, reliability, improvements justified by evaluation |
| 15 | Portfolio | planned | repo understandable by a stranger |

Completed phases are not re-described here. For what each one built, read ARCHITECTURE. For why, read DECISIONS (Phase 8: D-43 to D-46, E-5; Phase 9: D-47 to D-49; Phase 10: D-50 to D-52; Phase 11: D-53, D-54, E-6). Git tags mark the end of phases (`phase-N`).

**Milestones reached:** 1 backend foundation (Phase 2), 2 AI knowledge pipeline (Phase 4), 3 working AI assistant (Phase 6), 4 evaluated system (Phase 7), 5 automated ingestion (Phase 8), 6 usable product in a browser (Phase 9), 7 complete local product (Phase 10), 8 containerized product (Phase 11).
**Milestones ahead:** 9 cloud deployment (Phase 13).

---

## Phase 11 result (2026-10-26)

Built: a root `Dockerfile` (API and `migrate`), `ui/Dockerfile`, a rewritten `airflow/Dockerfile`, one `docker-compose.yml` for the whole system, a `.dockerignore`, a new `.env.example` (two required values). Removed: `airflow/docker-compose.yaml`, `airflow/docker-compose.official.yaml`, `airflow/Dockerfile.dockerignore`. Radar: no decision changed; the Phase 11 plan was widened after an audit (Airflow joined the one compose, which supersedes parts of D-43 and D-44).
Exit conditions: E1 one command starts everything and the model is ready: passed. E2 `e2e_check` passes against the containers: passed (11 checks). E3 the model loads offline (`HF_HUB_OFFLINE=1` in both images): passed. E4 no token in an image environment or build history: passed. E5 cold start by following the README on a clean machine: **waived by the owner, to run on another PC**. E6 check and CI green: passed; docs within the size budget: **waived** (README 10,046, ROADMAP 13,454, ARCHITECTURE 32,442, DECISIONS 43,735 bytes, against about 8,000, 12,000, 20,000, 30,000).
Parked: CI image build, authentication (Phase 12), merging the two images that both carry the embedding model (Phase 12 or 14), tests of the Streamlit screens, a failure-reason column.

## Phase 12: AWS deployment

**Goal:** the same architecture on AWS: EC2 (API, UI, and Airflow from the same compose), RDS PostgreSQL with pgvector, S3, IAM, CloudWatch. Gemini stays external.

- Map local to cloud, do not redesign: MinIO to S3 (`MINIO_ENDPOINT` unset), PostgreSQL to RDS (`DATABASE_URL`), the images as they are.
- Measured sizes (E-6): API image 5.5 GB, Airflow image 9.4 GB, UI 0.7 GB. Idle memory about 2.4 GiB, one ingestion adds about 4.3 GiB, so choose a machine with 16 GB and at least 50 GB of disk. Estimate the cost first.
- The embedding model is gated: building the images needs `HF_TOKEN`. Decide where the build happens (locally with a push to a private registry, or on the instance). Never push these images to a public registry.
- The same Alembic migrations run on RDS; the pgvector version depends on the RDS engine version, so check it.
- Decide then whether the free Gemini tier is acceptable or a paid key is needed. Recheck the model's shutdown date and re-read the data-retention terms of the Interactions API (D-29, D-36).
- **Authentication decision before anything is exposed:** upload, delete and the Airflow UI (default login) must not be reachable by anyone. Secrets move from `.env` to a secret store; close the published database and Airflow ports.

**Exit:** the core workflow works remotely, proven by `scripts/e2e_check.py` against the remote URL.

## Phase 13: Terraform

**Goal:** recreate the AWS infrastructure from code, after understanding it manually in Phase 12.

**Exit:** the infrastructure can be rebuilt from the configuration.

## Phase 14: Production quality

**Goal:** logging, error handling, configuration, tests, monitoring, reproducibility, deployment reliability. RAG improvements (hybrid retrieval, reranking, better chunking, prompt changes, filtering) only if evaluation evidence justifies them. Rerun `scripts/evaluate.py` against `data/eval/results/` before and after any such change.

## Phase 15: Portfolio

**Goal:** README, architecture diagram, setup and deployment instructions, screenshots, a demo with fictional or openly licensed documents, evaluation results, key decisions, limitations, future work. The README tells the story: problem, solution, architecture, RAG pipeline, technology choices, evaluation, deployment, lessons learned.

---

## Backlog (small items, no phase yet)

- Ripple-check script: search all docs for a changed term (the standards say automate it once it has failed twice).
- Security pass before Phase 12: upload size and type limits, authentication (upload, delete, Airflow UI), one prompt-injection case in the evaluation set.
- Structured logs (request id, latency, token counts): Phase 14.
- Second-model check of the evaluation before any "evaluated system" claim on a CV.
- Failure reason: only in the Airflow task log. Add a `documents.error` column only if a real need appears (D-47).
- UI: the screens have no automated tests, only the API client has (D-48). Streamlit's own app-testing tool is the candidate.
- Test warning: `starlette.testclient` asks for `httpx2` instead of `httpx`. Harmless today.
- Containers: CI does not build the images (the gated model needs a token). The two images each carry the embedding model (14.9 GB together): merge only if disk or build time hurts. The memory margin is thin on an 8 GB VM (about 1 GiB at the ingestion peak); an answer during an ingestion and a much larger PDF were not measured.
- Ingestion edge cases: a document that kills the worker is reset and retried at every run (no attempt counter); the reset of stuck documents assumes no manual ingestion runs at the same time.
- Cold start: the first run of an ingestion task took about 66 s before the work started (E-5). Measure again on an SSD or on AWS before tuning anything.
- Duplicate uploads: the same file uploaded twice creates twin chunks, which halves the effective `top_k`. Decide a rule (content hash at upload) before the corpus grows.
- Map `ValueError` from services to an HTTP error for callers that skip the schemas.
- Check accent display in PowerShell 5.1.
- Evaluation gaps: source matching is page-level, so a chunk on the right page counts even if it lacks the fact; a qualified answer (q16, q24) is judged by hand. Literal fact matching was tried and rejected (D-41).
- Typos in expected facts of `questions.json` (q02 "untilyou", q45 "givenas"); "10-2027" typo in `data/corpus/SOURCES.md`; the Dress Code and Handbook PDFs share the document id NS-HR-POL-005.

---

## Priority rules

1. Core AI functionality, 2. data pipeline, 3. backend integration, 4. evaluation, 5. orchestration, 6. UI, 7. containers, 8. cloud, 9. infrastructure as code, 10. advanced improvements.

If a later phase blocks understanding of an earlier one, go back. A phase is done when it works and I can explain it, not when the tool is installed.

## What must not happen

No Kubernetes, microservices, Kafka, agents, fine-tuning or separate vector database without a measured requirement. No hybrid retrieval without evaluation evidence. No elaborate frontend. No technology added for CV keywords.

> Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.
