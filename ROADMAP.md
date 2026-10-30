# ROADMAP

**Question this file answers:** what are we building, in what order, and where are we now?
**Not here:** how the system works today (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff (read this first)

Updated: 2026-10-30, Phase 12 done (tag `phase-12`, set after the docs commit). Phase 13 has not started.

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Current phase:** none running. Next is Phase 13 (Terraform): step 1 is the radar, then write its plan, exit conditions and exchange limit here before any code (WORKING_AGREEMENT section 5).
- **What works today:**
  - Local: one command, `copy .env.example .env`, set `HF_TOKEN` and `GEMINI_API_KEY`, then `docker compose up -d --build`. PostgreSQL, MinIO, `migrate`, `api`, `ui` and Airflow, with the code and the models baked into the images (D-53, D-54).
  - AWS (built by hand in `eu-north-1`, verified 2026-10-30): one EC2 instance runs the same compose plus `docker-compose.aws.yml`; RDS PostgreSQL 18.3 with pgvector 0.8.1; S3 bucket. Access only through an SSM tunnel, no inbound port (D-55 to D-60). On the server `scripts/e2e_check.py` printed `ALL CHECKS PASSED` (10 PASS lines), the 14 corpus PDFs were ingested, a question was answered with citations and an unanswerable one was refused. Numbers: DECISIONS E-7.
  - Last verified 2026-10-30: `scripts/check.ps1` 261 passed, none skipped; CI green on commit `f7395fc`.
- **AWS state now:** EC2 and RDS are **stopped** (since 2026-10-30). A stopped RDS restarts by itself after 7 days (about 2026-11-06): stop it again or delete it. Both disks still bill a little. Credits $140.00, 183 days left, the Free plan ends 2027-04-29 and the account closes then unless upgraded to Paid (credits stay valid 12 months from sign-up, checked 2026-10-29). Resource list and restart steps: ARCHITECTURE section 12.
- **What does not exist yet:** Terraform, authentication in the app (access is closed by the network, not by a login), CloudWatch, a restricted IAM user (the CLI uses the account's full-access role), automated tests of the Streamlit screens, a failure-reason column, an image build in CI, an e2e run from the laptop through the tunnel.
- **Run it:** README. Development outside Docker: start only `postgres minio minio-init` and run the API and UI on the host.
- **Data state:** the 14 corpus PDFs in `data/corpus/` are `processed` locally (302 chunks at the Phase 10 check) and were ingested on AWS. Evaluation set: `data/eval/questions.json` (version 5, 52 questions). Kept runs: `data/eval/results/`. Numbers: DECISIONS E-4 to E-7.
- **LLM:** `gemini-3.5-flash-lite` on the free tier; no shutdown date announced when checked 2026-10-25. Limits: `docs/provider_limits.md`. Data-use terms: D-36.
- **Rules in force:**
  - Only fictional or openly licensed documents go to Gemini (free tier may use the data), also in manual and e2e tests. The ISO 27001 PDF stays local. Never upload a personal file to test.
  - No similarity threshold (D-33), hybrid search, reranking or vector index: Phase 7 showed no need (E-4).
  - Any change to chunking, embeddings, the prompt or `top_k`: rerun `scripts/evaluate.py` and compare with `data/eval/results/`. One change per experiment.
  - The AI never writes citations; code builds them from stored chunks.
  - Airflow only schedules and runs; ingestion and status logic stay in `app/` (D-45). The code is baked into the images: after a change in `app/`, `scripts/`, `airflow/dags/`, `pyproject.toml` or `uv.lock`, rebuild (`docker compose up -d --build`; on AWS add `-f docker-compose.yml -f docker-compose.aws.yml`).
  - The UI is an HTTP client of the API and imports nothing from `app/` (I15).
  - A Docker build checks the real imports in the stage where the system libraries exist, and includes the database driver.
  - Rerun `scripts/e2e_check.py` after any change to ingestion, the API or the deployment, and against each new environment (`API_URL`).
  - AWS: no inbound rule on the server group and no public database; secrets only in `.env` (mode 600) on the server, never in Git or in chat; start RDS before EC2. The compose files contain the tags `!reset` and `!override`, so `check-yaml` runs with `--unsafe` (D-58).
  - Docs are changed once, at the end of a phase. In the middle of a phase only a decision record, and only when code depends on it.
  - Resources: the Docker VM and the AWS instance both have 8 GB. Idle use is about 2.4 GiB, one ingestion adds about 4.3 GiB (E-6, E-7): one ingestion at a time.
- **Next action:** Phase 13 step 1: the 30-minute radar (Terraform provider and Free plan limits), then the plan, exit conditions and limit.
- **Open questions:**
  1. Phase 11 E5 (the stranger test on a clean machine) is **waived** and will be run on another PC. Until then the README, including its AWS section, is **unverified**.
  2. Phase 12 E6 (measured cost) is **pending**: on 2026-10-30 the credits page showed $140.00 remaining and $0.00 used, but its estimates update about every 24 hours. Read **Total amount used** at https://settings.aws.com/billing/credits and record it in E-7 at the end of Phase 13.
  3. Not verified: whether the containers come back after an EC2 stop and start (the compose restart policies are `on-failure` for the apps). Check at the next start and record it.
  4. The e2e script printed 10 PASS lines on AWS; earlier docs said 11 checks. Read the script and settle the number (backlog).
  5. Phase 13 decides: recreate the AWS resources with Terraform after deleting the manual ones, or import them (see Phase 13).
  6. Still unverified: the RapidOCR models offline (D-54).
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
| 13 | Terraform | planned | infrastructure recreated from code |
| 14 | Production quality | planned | logging, monitoring, reliability, improvements justified by evaluation |
| 15 | Portfolio | planned | repo understandable by a stranger |

Completed phases are not re-described here. What each built: ARCHITECTURE. Why: DECISIONS (Phase 8: D-43 to D-46, E-5; Phase 9: D-47 to D-49; Phase 10: D-50 to D-52; Phase 11: D-53, D-54, E-6; Phase 12: D-55 to D-60, E-7). Git tags mark the end of phases (`phase-N`).

**Milestones reached:** 1 backend foundation (Phase 2), 2 AI knowledge pipeline (4), 3 working AI assistant (6), 4 evaluated system (7), 5 automated ingestion (8), 6 usable product in a browser (9), 7 complete local product (10), 8 containerized product (11), 9 cloud deployment (12).
**Milestones ahead:** 10 infrastructure as code (Phase 13).

---

## Phase 12 result (2026-10-30)

Built by hand in `eu-north-1`: S3 bucket, IAM role and policy, two security groups, RDS PostgreSQL, one EC2 instance, a cost budget; `docker-compose.aws.yml` (commit `f7395fc`). Radar: the new Free plan limits the EC2 types, so the 16 GB plan was dropped for `m7i-flex.large` (8 GiB) with a swap file (D-59); pgvector is available on RDS PostgreSQL 18.
Exit conditions: E1 budget alert and no inbound rule on the server group: passed. E2 migration on RDS and images built on the instance: passed (three revisions applied; build finished within 10 minutes). E3 e2e on the server: passed (`ALL CHECKS PASSED`, upload to `processed` 160 s; corpus ingested; one answer with citations, one refusal), **run on the server against `localhost`, not from the laptop through the tunnel**; the UI was opened from the laptop through the tunnel and showed "Model: ready". E4 nothing reachable from the internet: passed **at console level** (0 inbound rules, database not public; no outside port scan). E5 resource inventory with delete order: passed (ARCHITECTURE section 12). E6 one day of measured cost: **pending** (open question 2). E7 check and CI green: passed.
Limit: about 40 exchanges, exceeded; CloudWatch was cut and moved to Phase 14 (D-60). Doc size budget: met in this commit (compressed).
Parked: restricted IAM user, secret store, CloudWatch, the optional EC2 reward credit (backlog).

## Phase 13: Terraform

**Goal:** recreate the AWS infrastructure from code (ARCHITECTURE section 12 lists what exists), after understanding it by hand in Phase 12.

- Step 1: radar (provider version, what the Free plan blocks). Then write the plan here.
- Decide before code: delete the manual resources and recreate them with Terraform (clean, proves the code, costs one rebuild of about 10 minutes plus the ingestion), or import them (keeps the data, hides mistakes). Default recommendation: recreate. Where the state file lives (local, git-ignored, is enough for one person).
- Keep it to the resources already in use. No new AWS services.
- The Free plan ends 2027-04-29; Terraform is also the way back if the account is closed.

**Exit:** the infrastructure can be rebuilt from the configuration (`terraform apply` from nothing, then `scripts/e2e_check.py` passes) and removed with `terraform destroy`, leaving no resource behind.

## Phase 14: Production quality

**Goal:** logging, error handling, tests, monitoring (CloudWatch logs and alarm), reproducibility, deployment reliability. RAG improvements (hybrid retrieval, reranking, chunking, prompt, filtering) only if evaluation justifies them: rerun `scripts/evaluate.py` against `data/eval/results/` before and after.

## Phase 15: Portfolio

**Goal:** README, architecture diagram, setup and deployment instructions, screenshots, a demo with fictional or openly licensed documents, evaluation results, key decisions, limitations, future work.

---

## Backlog (small items, no phase yet)

- Security: a restricted IAM user for the CLI instead of the full-access role; secrets from a secret store instead of `.env`; authentication if real users appear; one prompt-injection case in the evaluation set; upload limits review.
- AWS: cost number into E-7 (open question 2); optional reward credits ($20 for launching and terminating a `t3.micro`; Bedrock and Lambda are outside the project); an e2e run from the laptop through a tunnel to port 8000.
- Ripple-check script: search all docs for a changed term (automate once it has failed twice).
- Settle the e2e check count (10 on AWS against 11 in older docs).
- `airflow/README.md` says "Phase 12 decides access": update it with D-56.
- Recheck the Gemini model shutdown date and the Interactions API retention terms (D-28, D-29): planned for the Phase 12 radar, not done.
- Structured logs (request id, latency, token counts): Phase 14.
- Second-model check of the evaluation before any "evaluated system" claim on a CV.
- Failure reason only in the Airflow log: add `documents.error` only if a real need appears (D-47).
- UI screens have no automated tests (candidate: Streamlit's app-testing tool).
- Containers: CI does not build the images (gated model); two images each carry the embedding model; thin memory margin on 8 GB (the AWS peak sample was 7.1 GiB used with 642 MiB swap, E-7); an answer during an ingestion and a much larger PDF were not measured.
- Ingestion: a document that kills the worker is retried at every run (no attempt counter); the reset assumes no manual ingestion runs at the same time. First-run task start-up about 66 s (E-5): measure again before tuning.
- Duplicate uploads create twin chunks and halve the effective `top_k`: decide a rule (content hash) before the corpus grows.
- Map `ValueError` from services to an HTTP error.
- Windows: VMware needs the hypervisor features off and Docker needs them on; note it in the setup if it bites again.
- Test warning: `starlette.testclient` asks for `httpx2`. Harmless today.
- Evaluation gaps: page-level source matching; qualified answers judged by hand (D-41). Typos in `questions.json` (q02, q45), in `data/corpus/SOURCES.md` ("10-2027"); two corpus PDFs share the document id NS-HR-POL-005.

---

## Priority rules

1. Core AI functionality, 2. data pipeline, 3. backend integration, 4. evaluation, 5. orchestration, 6. UI, 7. containers, 8. cloud, 9. infrastructure as code, 10. advanced improvements.

If a later phase blocks understanding of an earlier one, go back. A phase is done when it works and I can explain it, not when the tool is installed.

## What must not happen

No Kubernetes, microservices, Kafka, agents, fine-tuning or separate vector database without a measured requirement. No hybrid retrieval without evaluation evidence. No elaborate frontend. No technology added for CV keywords.

> Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.
