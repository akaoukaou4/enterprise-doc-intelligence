# ROADMAP

Question this file answers: what was built, in what order, and what is still open?
Not here: how the system works (ARCHITECTURE), why a choice was made (DECISIONS), how to run it (README), scope (PROJECT).

---

## Handoff

Updated: 2026-11-05. Phase 15 done (tag `phase-15`). The project is in its final state. No phase is running.

- **Product:** upload PDFs, ask questions, get grounded answers with document, page and section citations, or a clear "not found".
- **Repository:** public under akaoukaou4, MIT License, commit history rewritten once before publication (D-68).
- **Local:** `docker compose up -d --build` starts the whole system (README). Verified by the author on Windows.
- **AWS:** nothing exists now. The infrastructure is Terraform code in `infra/`. Verified by the author: applied, end-to-end checked (10 checks, server), destroyed (Phase 13). Rebuild steps: ARCHITECTURE section 12.3.
- **Checks:** `scripts/check.ps1` runs lint, format, 273 tests and the Terraform checks. CI runs the same on every push and is green.
- **Data:** 15 fictional PDFs in `data/corpus/`, 307 chunks. Evaluation set version 6: 53 questions (48 answerable, 5 to refuse). Results for E-9 are in DECISIONS; local run files are git-ignored.
- **LLM:** `gemini-3.5-flash-lite` on the free tier. Last checked 2026-11-01 (D-28, D-29). Recheck before any real use.
- **AWS cost and plan:** about $1 of credits used for Phases 12 and 13 (E-9). The Free plan ends 2027-04-29 and the account closes then unless upgraded.

### Verification status (what is and is not proven)

- Verified by the author on Windows (local stack) and on AWS (end-to-end check on the server).
- **Not verified:** a second person following the README on a clean machine. This is not passed. It is open question 1.

### Rules in force

- Only fictional or openly licensed documents go to Gemini (free tier may use the data, D-36). Never upload a personal file to test.
- Citations are built by code from stored chunks. The model returns only source numbers (I7).
- No similarity threshold, hybrid search, reranking or vector index without measured evidence (D-07, D-33, E-4, E-9).
- Logs never hold question, answer or chunk text, and never a query string (I9, D-35, D-62).
- Bad user input raises `ValidationFailedError` (422). A `ValueError` is an internal bug and returns 500 (D-63).
- Duplicate uploads are refused by content hash (409) (D-65).
- A document claimed three times and still processing is marked `failed` and not claimed again (D-64).
- Airflow schedules and runs; ingestion and status logic stay in `app/` (D-45).
- Any change to `app/`, `scripts/`, `airflow/dags/`, `pyproject.toml`, `uv.lock` or `Dockerfile` needs an image rebuild.
- Any change to chunking, embeddings, the prompt or `top_k`: rerun `scripts/evaluate.py` and compare. One change per experiment. Padding varies between runs (E-9).
- AWS: no inbound rule on the server group, no public database, `.env` on the server written from hidden prompts (mode 600), never in Git or chat. Destroy what is not in use.
- Terraform: secrets only through `TF_VAR_rds_password` and `TF_VAR_budget_email`, set in the terminal. The state file is local, git-ignored, and holds the database password. `force_destroy` and `skip_final_snapshot` are allowed only for the fictional corpus (D-61).
- Git: no personal email and no AI co-author trailer in commits. The `commit-msg` hook in `.git/hooks` enforces this (D-68). Install it in each new repository.
- Docs are changed once, at the end of a phase.

---

## Open questions

1. **Second-machine test (stranger test).** Not done. The README states this. It becomes "verified on two clean machines" only after someone outside the author follows the Quick start and reports the result.
2. **`terraform apply` on a machine with no local state.** Not verified. The code has been applied from one machine only.
3. **Server subnet pick.** `infra/ec2.tf` uses `sort(data.aws_subnets.default.ids)[0]`. Before the next apply, run `terraform plan` and confirm it creates the server and does not replace it. Not checked with a plan.
4. **Database Insights and RDS extended support.** Set by AWS defaults in the plan, not chosen by us. Their cost is not verified.
5. **RapidOCR models offline (D-54).** Not verified.
6. **Live kill test of the attempt counter (Phase 14 E2).** Waived. The rule is proven on real PostgreSQL by three integration tests.
7. **Docs size budget.** Waived for the fifth phase in a row. The docs are longer than their budgets; compression needs a decision that the risk of losing content is worth it.
8. **First rebuild after Phase 14 took about 73 minutes.** Cause not proven, probably a lost build cache on a hard disk. If a later code-only rebuild is slow, investigate.
9. **Gemini 503 retry.** Not built. On 2026-11-04 two of six questions failed with 503 "high demand" in one afternoon. D-30 says to retry once for transient 5xx if they appear; they have. Build it only with a new decision and a rerun of the end-to-end check.
10. **Phase 14 understanding session.** Pending. The owner explains the Phase 14 points back in their own words before the phase is closed.

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
| 6 | Gemini and RAG | done | grounded answer with citations, or a clear refusal |
| 7 | Evaluation | done | repeatable measurement of quality |
| 8 | Airflow | done | ingestion starts by itself after upload |
| 9 | Streamlit UI | done | full use without calling the API by hand |
| 10 | Complete local system | done | everything works locally, checked by one script |
| 11 | Containerization | done (E5 waived) | the whole system starts with one Docker command |
| 12 | AWS deployment | done (cost closed, about $1) | core workflow works remotely |
| 13 | Terraform | done | infrastructure recreated from code |
| 14 | Production quality | done (E2 waived, CloudWatch moved to backlog) | logging, reliability, improvements justified by evidence |
| 15 | Portfolio | done (tag `phase-15`) | repo understandable by a stranger; second-machine test open (question 1) |

Completed phases are not re-described here. What each built: ARCHITECTURE. Why: DECISIONS (Phase 8: D-43 to D-46, E-5; Phase 9: D-47 to D-49; Phase 10: D-50 to D-52; Phase 11: D-53, D-54, E-6; Phase 12: D-55 to D-60, E-7; Phase 13: D-61, E-8; Phase 14: D-62 to D-67, E-9; Phase 15: D-68).

**Milestones reached:** 1 backend foundation (Phase 2), 2 AI knowledge pipeline (4), 3 working AI assistant (6), 4 evaluated system (7), 5 automated ingestion (8), 6 usable product in a browser (9), 7 complete local product (10), 8 containerized product (11), 9 cloud deployment (12), 10 infrastructure as code (13), 11 production-quality system (14), 12 portfolio-ready repository (15).

---

## Phase 13 result (2026-10-31)

Terraform 1.16.6 and AWS provider 6.71.0. Exit conditions: apply from nothing passed (13 resources, then the budget); e2e check on the server passed (10 checks, processed after 170 s); destroy left nothing passed; the budget in code passed. Limits and details: DECISIONS D-61, E-8.

## Phase 14 result (2026-11-01 to 2026-11-02)

Goal: reliability and diagnosability, using only changes that answer a named weakness. Delivered: Terraform checks in `check.ps1` and CI (done); services raise `ValidationFailedError` (done); request id and one log line per request (done, and a live log line was read, which showed uvicorn's access log leaked the query string, so it is off); attempt counter (done by integration tests, live kill test waived); duplicate upload refused by content hash (done, live 409 checked); one prompt-injection case (passed, one case only); CloudWatch (moved to backlog, D-67). Evaluation with 15 documents: no change in retrieval (E-9). Details: DECISIONS D-62 to D-67, E-9.

## Phase 15 result (2026-11-04 to 2026-11-05)

Goal: a repository a stranger can understand, and a CV built from evidence.

Delivered:
- Career check: 25 postings read. Demand matches the stack (RAG, vector stores, FastAPI, Python, Docker, AWS, Terraform). Gaps (agents, observability, Kubernetes) are named in the README as considered, not built.
- Screenshots (4) and a 52-second demo video, shown on GitHub.
- Public-readiness: MIT license under akaoukaou4; history scan for personal email addresses; history rewritten once so commits show the no-reply address and no AI co-author trailers. Commit count unchanged (87). Commit hashes changed. D-68.
- Protection against recurrence: a commit-msg hook that rejects Claude trailers and personal email addresses; the GitHub setting that blocks pushes exposing the email.
- README: rewritten in full, with tech stack, architecture (three diagrams), engineering decisions (chosen and considered-not-built), results with limits, run instructions, AWS summary, limitations.
- Tag `phase-15`.

Not done in this phase, by choice: CV bullets, GitHub profile and LinkedIn (done outside this project). The second-machine test (open question 1, recorded as not passed).

---

## Backlog and future improvements

- **Second-machine test:** follow the README on a clean machine and record the result (question 1).
- **Retry on Gemini 503:** one retry for transient 5xx, with a rerun of the end-to-end check (question 9, D-30).
- **Cloud:** CloudWatch logs for `api` and one alarm (D-67). The logs already go to stdout with a request id, so no application change is needed.
- **Security:** a restricted IAM user for the CLI instead of the full-access role; secrets from a secret store (SSM Parameter Store, D-57); authentication if real users appear; review upload limits.
- **Terraform:** `terraform plan` check that the server is not replaced (question 3); remote state only if a second person works on it; remove `force_destroy` and `skip_final_snapshot` before real data.
- **AWS:** check Database Insights and extended-support cost (question 4); an end-to-end run from the laptop through a tunnel to port 8000; whether containers return after an instance stop and start (the instance was destroyed, so check at the next deployment).
- **Attempt counter:** a live kill test (question 6); `reset_orphans` still assumes no manual ingestion at the same time. First-run task start-up about 66 s (E-5): measure again before tuning.
- **Duplicates:** a hash backfill for the 14 older documents (needs the files from storage); a near-duplicate rule (same text, different file) is not decided.
- **Request log:** nothing counts questions per minute or the error rate; add only with a monitoring need.
- **Model and API:** recheck the Gemini model shutdown date and the Interactions API retention terms before each real use (D-28, D-29).
- **Failure reason:** only in the Airflow log. Add `documents.error` only if a real need appears (D-47).
- **UI tests:** the Streamlit screens have no automated tests (candidate: Streamlit's app-testing tool).
- **Containers:** CI does not build the images (gated model); two images each carry the embedding model; thin memory margin on 8 GB; a question during ingestion and a much larger PDF were not measured.
- **Evaluation:** page-level source matching; qualified answers judged by hand (D-41); padding judged on one run is noisy (E-9); a harder, independently written question set before any claim of production quality.
- **Typos:** `questions.json` (q02, q45) and `data/corpus/SOURCES.md` ("10-2027"). Two corpus PDFs share the document id NS-HR-POL-005.
- **Windows:** VMware needs the hypervisor features off and Docker needs them on; the README mentions it in the development notes.
- **Test warning:** `starlette.testclient` asks for `httpx2`. Harmless today.

---

## Priority rules

1. Core AI functionality. 2. Data pipeline. 3. Backend integration. 4. Evaluation. 5. Orchestration. 6. UI. 7. Containers. 8. Cloud. 9. Infrastructure as code. 10. Advanced improvements.

If a later phase blocks understanding of an earlier one, go back. A phase is done when it works and the owner can explain it, not when the tool is installed.

## What must not happen

No Kubernetes, microservices, Kafka, agents, fine-tuning or separate vector database without a measured requirement. No hybrid retrieval without evidence from evaluation. No elaborate frontend. No technology added for CV keywords.

> Build the core AI system first. Make it reliable. Evaluate it. Then productionize and deploy it.
