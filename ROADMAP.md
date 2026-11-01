# ROADMAP

**Question this file answers:** what are we building, in what order, and where are we now?
**Not here:** how the system works today (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff (read this first)

Updated: 2026-10-31, Phase 13 done (tag `phase-13`, set after the docs commit). Phase 14 has not started.

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Current phase:** none running. Next is Phase 14 (production quality): radar, then write its plan, exit conditions and exchange limit here before any code (WORKING_AGREEMENT section 5).
- **What works today:**
  - Local: `copy .env.example .env`, set `HF_TOKEN` and `GEMINI_API_KEY`, then `docker compose up -d --build`. PostgreSQL, MinIO, `migrate`, `api`, `ui` and Airflow, code and models baked into the images (D-53, D-54).
  - AWS: **nothing exists right now.** The whole infrastructure is Terraform code in `infra/` (14 resources: S3, IAM, two security groups, RDS PostgreSQL 18.3, one EC2 instance, the budget). It was applied from nothing, ran the e2e check on the server (10 PASS lines), and was destroyed with `terraform destroy`; a read-only check found no instance, database, volume, security group, bucket or role left (D-61, E-8). Rebuild steps: ARCHITECTURE section 12.3.
  - Last full local check: `scripts/check.ps1` 261 passed, none skipped, on commit `f7395fc` (Phase 12). Phase 13 added only `infra/` and `.gitattributes`; the pre-push check runs once at the Phase 13 push.
- **AWS state and cost:** no resources, so no running cost and **no budget alert** until the next `terraform apply` (the budget is part of the code). Credits were $140.00 on 2026-10-30; the Free plan ends 2027-04-29 and the account closes then unless upgraded to Paid (credits stay valid 12 months from sign-up, checked 2026-10-29). Cost Explorer through 2026-10-30 showed a net of about $0.00 (E-8).
- **What does not exist yet:** CloudWatch logs and alarms, a restricted IAM user (the CLI uses the account's full-access role), a secret store for the server's `.env`, authentication in the app (the network closes access), a failure-reason column, automated tests of the Streamlit screens, an image build in CI, `terraform fmt` and `validate` in `scripts/check.ps1` and CI, remote Terraform state.
- **Run it:** README. Development outside Docker: start only `postgres minio minio-init` and run the API and UI on the host.
- **Data state:** the 14 corpus PDFs in `data/corpus/` are `processed` locally (302 chunks at the Phase 10 check). On AWS the corpus was ingested in Phase 12, and the Phase 13 e2e used one test document; both disappeared with the destroy. Evaluation set: `data/eval/questions.json` (version 5, 52 questions). Kept runs: `data/eval/results/`. Numbers: DECISIONS E-4 to E-8.
- **LLM:** `gemini-3.5-flash-lite` on the free tier; no shutdown date announced when checked 2026-10-25, **not rechecked** in Phases 12 and 13. Limits: `docs/provider_limits.md`. Data-use terms: D-36.
- **Rules in force:**
  - Only fictional or openly licensed documents go to Gemini (free tier may use the data), also in manual and e2e tests. The ISO 27001 PDF stays local. Never upload a personal file to test.
  - No similarity threshold (D-33), hybrid search, reranking or vector index: Phase 7 showed no need (E-4).
  - Any change to chunking, embeddings, the prompt or `top_k`: rerun `scripts/evaluate.py` and compare with `data/eval/results/`. One change per experiment.
  - The AI never writes citations; code builds them from stored chunks.
  - Airflow only schedules and runs; ingestion and status logic stay in `app/` (D-45). The code is baked into the images: after a change in `app/`, `scripts/`, `airflow/dags/`, `pyproject.toml` or `uv.lock`, rebuild (on AWS add `-f docker-compose.yml -f docker-compose.aws.yml`).
  - The UI is an HTTP client of the API and imports nothing from `app/` (I15).
  - A Docker build checks the real imports in the stage where the system libraries exist, and includes the database driver.
  - Rerun `scripts/e2e_check.py` after any change to ingestion, the API or the deployment, and against each new environment (`API_URL`).
  - AWS: no inbound rule on the server group and no public database; the `.env` on the server (mode 600) is written from hidden prompts, its value lengths checked before writing, and it is never in Git or chat; destroy what is not in use.
  - Terraform: secrets only as `TF_VAR_rds_password` and `TF_VAR_budget_email`, set in the terminal; the state file is local, git-ignored, and holds the database password: never commit or share it. `force_destroy` on the bucket and `skip_final_snapshot` on RDS are allowed only for the fictional corpus: remove both before any real data (D-61). Before the first apply on an account with existing resources of the same names, delete or import them (a plan does not show name clashes).
  - Every command given in chat says where it runs (laptop terminal or server session).
  - Docs are changed once, at the end of a phase. In the middle of a phase only a decision record, and only when code depends on it. Each doc is delivered as one complete final file.
  - Resources: the Docker VM and the AWS instance both have 8 GB. Idle use is about 2.4 GiB, one ingestion adds about 4.3 GiB (E-6, E-7): one ingestion at a time.
- **Next action:** Phase 14 step 1: the 30-minute radar (Gemini model shutdown date and Interactions API retention terms, both unchecked since 2026-10-25; CloudWatch pricing and the Free plan), then write the plan, exit conditions and limit here.
- **Open questions:**
  1. Phase 11 E5 (the stranger test on a clean machine) is **waived**; it will be run on another PC. Until then the README, including its AWS section, is **unverified**.
  2. Phase 12 E6 (measured cost) is **pending**. Cost Explorer shows about $0.00 net through 2026-10-30, but the last day may be incomplete and it is not the credits page. Read **Total amount used** at https://settings.aws.com/billing/credits (after the 24-hour lag) and record it in E-8.
  3. Not verified: a `terraform apply` on another machine with no local state (the code has been applied from this machine only).
  4. Not verified: the cost of "Database Insights - Standard" and of RDS extended support. The Terraform-built database showed both as AWS defaults (`database_insights_mode = standard`, `engine_lifecycle_support = open-source-rds-extended-support`); we did not set them.
  5. Not verified: the RapidOCR models offline (D-54).
  6. The server's subnet comes from the first id of the default VPC's subnet list. It applied correctly in Phase 13 (it was not the subnet the manual build used), but the list order is not guaranteed; a change would replace the instance. A `sort(...)` was planned and not applied (backlog).
  7. The doc size budget is **waived** (see the Phase 13 result). Compression is a candidate step of Phase 14, only with a decision that it is worth the risk of losing content.
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
| 8 | Airflow | done | ingestion starts by itself after upload |
| 9 | Streamlit UI | done | full use without calling the API by hand |
| 10 | Complete local system | done | everything works locally, checked by one script |
| 11 | Containerization | done (E5 waived) | the whole system starts with one Docker command |
| 12 | AWS deployment | done (E6 pending) | core workflow works remotely |
| 13 | Terraform | done | infrastructure recreated from code |
| 14 | Production quality | planned | logging, monitoring, reliability, improvements justified by evaluation |
| 15 | Portfolio | planned | repo understandable by a stranger |

Completed phases are not re-described here. What each built: ARCHITECTURE. Why: DECISIONS (Phase 8: D-43 to D-46, E-5; Phase 9: D-47 to D-49; Phase 10: D-50 to D-52; Phase 11: D-53, D-54, E-6; Phase 12: D-55 to D-60, E-7; Phase 13: D-61, E-8). Git tags mark the end of phases (`phase-N`).

**Milestones reached:** 1 backend foundation (Phase 2), 2 AI knowledge pipeline (4), 3 working AI assistant (6), 4 evaluated system (7), 5 automated ingestion (8), 6 usable product in a browser (9), 7 complete local product (10), 8 containerized product (11), 9 cloud deployment (12), 10 infrastructure as code (13).
**Milestones ahead:** 11 production-quality system (Phase 14), 12 portfolio (Phase 15).

---

## Phase 13 result (2026-10-31)

Terraform 1.16.6 and AWS provider 6.71.0 in `infra/`. Radar: no decision changed; versions were read from the winget package, the provider from `terraform init`.
Exit conditions: E1 apply from nothing: **passed** (13 resources, then the budget; RDS took 7 min 29 s; the manual resources were deleted first, by exact id). E2 e2e check on the result: **passed** (10 PASS lines, `ALL CHECKS PASSED`, `processed` after 170 s), run **on the server against `localhost`**, not through the tunnel. E3 destroy leaves nothing: **passed** (14 destroyed; read-only listings found no instance, database, volume, security group, bucket or role, and no budget). E4 budget in code: **passed** (same $20 and three alerts as the manual one).
Limit: about 40 exchanges, reached; the docs were done at the end of the phase as agreed. Doc size budget: **waived** for the fourth phase in a row. Measured at the docs commit: README 13,009, ARCHITECTURE 30,312, DECISIONS 34,815 bytes (budgets about 8,000, 20,000, 30,000); ROADMAP was also over its budget of about 12,000 (14,535 bytes in the draft before this wording). ARCHITECTURE was kept long on purpose to avoid losing content.
Parked: remote state, a `terraform fmt` check in CI, a restricted IAM user, CloudWatch.

## Phase 14: Production quality

**Goal:** logging, error handling, tests, monitoring (CloudWatch logs and one alarm), reproducibility, deployment reliability. RAG improvements (hybrid retrieval, reranking, chunking, prompt, filtering) only if evaluation justifies them: rerun `scripts/evaluate.py` against `data/eval/results/` before and after.

Candidates, each needing a named decision it changes (ENGINEERING_STANDARDS section 1): structured logs (request id, latency, token counts); CloudWatch logs for `api` and one alarm (D-60); an attempt counter for documents that kill the worker (D-45); a secret store for the server `.env` (D-57); a restricted IAM user; `terraform fmt` and `validate` in the check and CI; one prompt-injection case in the evaluation set; the Gemini model shutdown date and retention terms recheck. Write the chosen subset and the exit conditions here at the start of the phase.

## Phase 15: Portfolio

**Goal:** README, architecture diagram, setup and deployment instructions, screenshots, a demo with fictional or openly licensed documents, evaluation results, key decisions, limitations, future work. A deployed demo for others is a recording, not a link (D-56).

---

## Backlog (small items, no phase yet)

- Security: a restricted IAM user for the CLI instead of the full-access role; secrets from a secret store; authentication if real users appear; one prompt-injection case in the evaluation set; upload limits review.
- Terraform: pick the server subnet in a stable way (`sort(...)` of the subnet ids, or a fixed id) and plan before applying; `terraform fmt -check` and `validate` in `scripts/check.ps1` and CI; remote state only if a second person works on it; `force_destroy` and `skip_final_snapshot` removed before real data.
- AWS: cost number into E-8 (open question 2); check "Database Insights" and extended-support cost; optional reward credits ($20 for launching and terminating a `t3.micro`); an e2e run from the laptop through a tunnel to port 8000; whether containers return after an instance stop and start (the instance was destroyed, so check at the next deployment).
- Recheck the Gemini model shutdown date and the Interactions API retention terms (D-28, D-29).
- Ripple-check script: search all docs for a changed term (it failed three times now, so build it).
- Structured logs (request id, latency, token counts): Phase 14.
- Second-model check of the evaluation before any "evaluated system" claim on a CV.
- Failure reason only in the Airflow log: add `documents.error` only if a real need appears (D-47).
- UI screens have no automated tests (candidate: Streamlit's app-testing tool).
- Containers: CI does not build the images (gated model); two images each carry the embedding model; thin memory margin on 8 GB (AWS peak sample 7.1 GiB used with 642 MiB swap, E-7); an answer during an ingestion and a much larger PDF were not measured.
- Ingestion: a document that kills the worker is retried at every run (no attempt counter); the reset assumes no manual ingestion at the same time. First-run task start-up about 66 s (E-5): measure again before tuning.
- Duplicate uploads create twin chunks and halve the effective `top_k`: decide a rule (content hash) before the corpus grows.
- Map `ValueError` from services to an HTTP error.
- Windows: VMware needs the hypervisor features off and Docker needs them on; the README mentions it.
- Test warning: `starlette.testclient` asks for `httpx2`. Harmless today.
- Evaluation gaps: page-level source matching; qualified answers judged by hand (D-41). Typos in `questions.json` (q02, q45) and in `data/corpus/SOURCES.md` ("10-2027"); two corpus PDFs share the document id NS-HR-POL-005.

---

## Priority rules

1. Core AI functionality, 2. data pipeline, 3. backend integration, 4. evaluation, 5. orchestration, 6. UI, 7. containers, 8. cloud, 9. infrastructure as code, 10. advanced improvements.

If a later phase blocks understanding of an earlier one, go back. A phase is done when it works and I can explain it, not when the tool is installed.

## What must not happen

No Kubernetes, microservices, Kafka, agents, fine-tuning or separate vector database without a measured requirement. No hybrid retrieval without evaluation evidence. No elaborate frontend. No technology added for CV keywords.

> Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.
