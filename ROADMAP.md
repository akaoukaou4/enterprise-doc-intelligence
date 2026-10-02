# Enterprise AI Document Intelligence Platform: V1 Roadmap

> **Companion to:** `PROJECT.md` (the vision). This file is the **execution plan**: what we build, in what order, and how we know a phase is done.
> **Scope:** Phase 0 (environment) to the end of V1. Nothing from V2/V3.
> **Last updated:** 2026-10-02
> **Current phase:** Phase 0, Environment preparation (0.1 to 0.3 done; next: 0.4 Python project setup)
> **Locked stack decisions:** embeddings = `google/embeddinggemma-300m` (local, 768 dims, multilingual) · LLM = Gemini Flash-Lite family (free tier) · Postgres + pgvector in Docker · UI = Streamlit

---

## How to use this file

- This is a **living document**. After every work session we update: checkboxes, the progress table, the decision log, and the changelog at the bottom.
- Status legend: `⬜ Not started` · `🟨 In progress` · `✅ Done` · `⏸️ Blocked`
- A phase is only **Done** when its **Definition of Done (DoD)** is fully met, not when the code "kind of works".
- Rule of the project: **make it work simply, then make it robust, then (only if needed) make it fancy.**
- Every phase ends with a **git commit/tag** (e.g. `phase-3-done`) so we can always roll back to a known-good state.
- New to a term (token, parameter, dimension, chunk...)? See the **Learning glossary** below the decision details.

---

## Progress dashboard

| # | Phase | Status | Key deliverable |
|---|-------|--------|-----------------|
| 0 | Environment preparation | 🟨 | 0.1 to 0.3 done (machine, accounts, repo). Next: 0.4 to 0.6 (Python project, Docker services, tooling and CI) |
| 1 | Project skeleton and FastAPI foundation | ⬜ | Running API with config, logging, health check, tests |
| 2 | Storage and database layer | ⬜ | Upload a PDF → stored in S3/MinIO + metadata in Postgres |
| 3 | Document processing (extract, clean, chunk) | ⬜ | PDF → clean, page-aware chunks (~350 tokens) |
| 4 | Embeddings and vector store | ⬜ | Chunks embedded locally with EmbeddingGemma and stored in pgvector |
| 5 | Retrieval | ⬜ | Question → top-k relevant chunks, with a small eval set |
| 6 | Generation (RAG) and citations | ⬜ | `/ask` returns grounded answer + sources |
| 7 | Orchestration with Airflow | ⬜ | Ingestion runs as a DAG with visible status |
| 8 | Demo UI (Streamlit) | ⬜ | Web page to upload, track status, ask, see cited sources |
| 9 | Hardening: tests, errors, quality | ⬜ | Reliable, tested, documented failure modes |
| 10 | Full Dockerization | ⬜ | Whole stack starts with one command |
| 11 | Deploy to AWS | ⬜ | App reachable online, costs under control |
| 12 | Documentation and portfolio polish | ⬜ | README, architecture diagram, demo, lessons learned |

---

## Decision log (tech stack for V1)

Every technology must solve a real problem in the current project. "Decided" items are locked unless a measured problem forces a change (and then we log it here).

| Problem | Choice | Why | Status |
|---------|--------|-----|--------|
| Language / runtime | Python 3.12 | Standard for AI/data, best library support | Proposed |
| Dependency management | `uv` | Fast, lockfile, reproducible | Proposed |
| API framework | FastAPI + Pydantic | Already in vision; validation built in | Decided |
| Metadata DB | PostgreSQL | Industry standard, relational metadata | Decided |
| Vector store | **pgvector** (inside the same Postgres), `vector(768)` | One database for metadata and vectors. Simpler than a separate vector DB, plenty for V1 scale | Decided |
| Object storage | AWS S3 (**MinIO locally** in Docker) | Same S3 API locally and in the cloud, no AWS cost during development | Proposed |
| Migrations | Alembic | Schema changes tracked in git | Proposed |
| PDF extraction | PyMuPDF (`pymupdf`) | Fast, keeps page numbers, good text quality | Proposed |
| **Embeddings** | **`google/embeddinggemma-300m`**, run locally on CPU, 768 dims, behind an `EmbeddingService` interface. **No model comparison phase: this is the model** | Best quality we found that still fits a small CPU server (~1.25 GB RAM), multilingual (100+ languages), 2,048-token input. See D1 | Decided |
| **LLM** | **Gemini Flash-Lite family via Google AI Studio free tier**: `gemini-3.5-flash-lite` primary, `gemini-3.1-flash-lite` backup (config switch), behind an `LLMService` interface | Best *usable* free option: full Flash models are capped at ~20 requests/day on free keys, Flash-Lite at ~500/day. See D2 | Decided |
| Postgres hosting (cloud) | **Postgres + pgvector in Docker on the EC2 instance**, nightly `pg_dump` to S3. RDS = documented upgrade path | Cheapest; identical to local setup; RDS burns credits. See D3 | Decided |
| Demo UI | **Streamlit** (Phase 8, committed) | Python-only, fastest route to a demo-able product. React frontend = V2 | Decided |
| Orchestration | Apache Airflow (**after** the pipeline already works as plain Python). Whether it runs in the cloud is decided in Phase 11 | Named in the vision; used only once there is a real pipeline to orchestrate | Decided (Phase 7), cloud part open |
| Containers | Docker + Docker Compose | Reproducible environment | Decided |
| Quality tooling | `ruff` (lint + format), `pytest`, `pre-commit`, GitHub Actions | Cheap, high-value professional habits | Proposed |
| Cloud deploy | AWS EC2 + Docker Compose + S3 | Simplest realistic deployment; avoids ECS/EKS complexity | Decided |

**Explicitly NOT in V1:** Kubernetes, Kafka, Terraform, LangGraph/agents, microservices, advanced observability, complex auth, AI gateways, custom model training.

### Decision details (researched 2026-09-30 and 2026-10-01)

> **Reality check on "free":** free tiers change often and Google no longer publishes its free-tier limits. The Gemini numbers below are *measured by a third party* (dated 2026-09-02). In Phase 0 we read **our own** real limits from the AI Studio console (or from the 429 error body) and record them in `docs/provider_limits.md`.
> **Data privacy:** embeddings run locally, so document text is not sent anywhere for indexing. But at answer time the question and the **retrieved chunks are sent to Gemini**, and Google's pricing page says free-tier requests may be used to improve its products. **During development, use only public/sample documents.** Sensitive documents would require a paid tier or a local LLM (Ollama) later.

#### D1: Embeddings, `google/embeddinggemma-300m`

**Verified on the official model card (2026-10-01):**

| Spec | Value |
|------|-------|
| Size | 300 million parameters (built from Gemma 3), about 1.2 GB as stored (32-bit numbers) |
| Output vector | **768 numbers** per text; can be shortened to 512, 256 or 128 (Matryoshka) with a small quality loss |
| Max input | **2,048 tokens** per text |
| Languages | Trained on 100+ spoken languages |
| Quality (Google-reported, 768d) | MTEB English v2: 69.67 · MTEB Multilingual v2: 61.15 · MTEB Code: 68.76 |
| Shortened vectors (English score) | 512d: 69.18 · 256d: 68.37 · 128d: 66.66 |
| License / access | Gemma terms of use; files are gated: **you must log in to Hugging Face and accept the license** before downloading |
| Numeric precision | **No float16** support: use float32 (or bfloat16 where hardware supports it) |
| Prompts | Texts are embedded with a short prefix depending on type: queries use `task: search result \| query: ...`, documents use `title: {title or "none"} \| text: ...`. The `sentence-transformers` library applies them via `encode_query` and `encode_document` |

**Third-party CPU measurement:** about 1.25 GB peak RAM and about 78 ms per sentence (roughly 36 sentences/second) on a 4-vCPU, 16 GB server in float32. One independent Portuguese-language benchmark also scored it above BGE-M3 (0.649 vs 0.616).

**Why this model (and why no comparison phase):** the question was "what is the strongest model that still fits a small cloud server?" The strongest open model overall (Qwen3-Embedding-8B, 4,096 dims, 32k input) needs GPU-class memory (roughly 16 GB for its weights alone), so it can't run on a cheap/free EC2 instance. The realistic alternatives, BGE-M3 (~568M parameters) and Qwen3-Embedding-0.6B, are about **twice the size, so about twice the RAM**, and their much longer input limits (8k / 32k tokens) are useless to us because we cut text into ~350-token chunks anyway. EmbeddingGemma-300m gives the best quality per megabyte of RAM and fixes both weaknesses of the earlier MiniLM idea (English-only, 256-token cap). It is not #1 on any leaderboard; it is the **best fit for our constraints**.

**What this choice means for the design (reflected in the phases):**

| Consequence | How we handle it |
|-------------|------------------|
| Input limit is 2,048 tokens | We deliberately use much smaller chunks (**~350 tokens, hard cap 512**): smaller, focused chunks retrieve more precisely than huge ones |
| Queries and documents need different prompts | Always call `encode_query` for questions and `encode_document` for chunks; pass the **document title** when we have it (the model card says it improves retrieval) |
| float32 on CPU needs about 1.2 to 1.3 GB RAM, loaded permanently (queries must be embedded at answer time too) | Load once at startup; **measure real memory in Phase 10**; this decides the EC2 size |
| Gated download | Hugging Face account + license accepted + read token in `.env` (Phase 0). The token is used at image *build* time only, never stored in the image or git |
| 768 numbers per chunk = about 3 KB | Storage is tiny (10,000 chunks ≈ 30 MB). If we ever need to shrink it, vectors can be cut to 512 (about 33% smaller) with a small quality loss |
| Gemma license | Fine for this project. We download the weights at build time and do **not** redistribute them in the repo. Keep the Gemma prohibited-use policy in mind |
| Speed | At roughly 36 chunks/second on a comparable CPU, a 300-chunk document embeds in roughly 10 seconds (to be measured in Phase 4) |

**Critical rule:** vectors from different models are **not comparable, even with the same dimension**. There is exactly one *active* embedding model per index. We store `embedding_model` with every chunk; if the model ever changes (a V2 decision), `scripts/reembed.py` re-embeds everything, never mixing.

#### D2: LLM, Gemini Flash-Lite on the free tier

**Correction to an early note of mine:** I first described Gemini's free tier as generous. Newer measurements show that is only true for the *Lite* models.

Measured on 2026-09-02 with a brand-new key and no billing (third-party measurement, so verify on your own key):

| Model | Requests/min | Requests/day |
|-------|--------------|--------------|
| `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash` | 5 | **20** |
| **`gemini-3.5-flash-lite`**, **`gemini-3.1-flash-lite`** | **15** | **500** |
| `gemini-2.5-*` models | closed to new users (404) | n/a |

Other facts that shape the design:
- Quota is counted **per project, not per key**, and the daily quota resets at **midnight Pacific time**.
- The full Flash models can be **very slow on the free tier** (measured 27 to 148 seconds per request, more under load). Flash-Lite is the practical choice; we still measure its latency in Phase 6.
- When you hit a limit, the 429 error body states the exact limit; we use that to read our real numbers.
- Free Google Search grounding is not available to new free keys (we don't need it: our answers must come from the documents).

**Decision:** `gemini-3.5-flash-lite` as primary, `gemini-3.1-flash-lite` as a config-only backup. Exact names are re-verified at the start of Phase 6 because model names change quickly.

**What 500 requests/day means for us:** each `/ask` uses one LLM call, so the budget is plenty for a student project, **but it is shared between development, evaluation and demos.** Rules: automated tests use a **fake LLM**; real calls are logged with a counter; the UI shows a friendly message when the daily quota is exhausted.

**Integration:** `LLMService` is a small interface. First try Gemini's OpenAI-compatible endpoint (reported as supported); if it lacks something we need, use the official `google-genai` SDK. Either way it stays behind the interface, so adding another provider later is a config-level change, not a rewrite. No second provider is required in V1.

#### D3: Postgres on EC2 vs. RDS, and AWS "free tier" in 2026

What changed: for accounts created **on or after 15 July 2025**, the old "12 months free EC2/RDS" program no longer exists. New accounts choose a **Free plan** with **$100 in credits (+ up to $100 more from 5 onboarding activities worth $20 each: launch EC2, configure RDS, Lambda, Bedrock, create a Budget)**. The plan lasts **6 months or until credits run out**, whichever comes first, and **EC2 and RDS usage is paid from those credits**.

| | Postgres in Docker on EC2 | Amazon RDS for PostgreSQL |
|---|---|---|
| Cost | Only the EC2 instance + disk | Separate hourly DB instance + storage on top of EC2 (burns credits faster) |
| pgvector | Yes (same image as local) | Yes (supported extension) |
| Backups / patching / failover | You (nightly `pg_dump` to S3, EBS snapshots) | Managed by AWS |
| Match with local setup | Identical | Needs different connection setup |
| Fit for V1 | **Best** | Better for real production |

**Decision:** Postgres + pgvector **in Docker on the EC2 instance** for V1, with nightly `pg_dump` to S3. RDS is the documented upgrade path: pgvector works there, so migrating later means a dump/restore and a new `DATABASE_URL`. Being able to explain *why* you didn't pick RDS (cost vs. operational burden) is itself a strong interview answer.

**AWS account and credits:** because the credit clock starts at signup, **we do not create the AWS account until just before Phase 11.** Phases 0 to 10 run entirely locally (MinIO replaces S3). **The cloud runs only what the live product needs**; the instance size is decided from real measurements (Phase 10) and the Airflow-in-the-cloud question is decided in Phase 11. Always check current instance prices on the AWS pricing page before launching.

#### D4: UI
Streamlit, built in Phase 8 (committed, not optional). It talks only to the public API, so a React frontend in V2 replaces it without touching the backend.

---

## Learning glossary

| Term | Plain-English meaning | Why it matters here |
|------|----------------------|---------------------|
| **Token** | A piece of text the model reads: a short word, or part of a longer one. Rule of thumb: 100 tokens ≈ 75 English words | Models have limits counted in tokens, not pages or words. Our ~350-token chunk is about 260 words, roughly half a page |
| **Parameter** | One learned number inside the model. "300M" = 300 million of them | More parameters usually means smarter but heavier. **Memory ≈ parameters × bytes per number**: 300M × 4 bytes (float32) ≈ 1.2 GB |
| **Embedding / vector** | A list of numbers that captures the *meaning* of a text. Texts with similar meaning get similar lists | This is how we search by meaning instead of by keywords |
| **Dimension** | The length of that list (768 for our model) | More dimensions = more detail but more storage (768 numbers ≈ 3 KB per chunk) |
| **Max input (context length)** | The most tokens the model can read in one go (2,048 for ours) | Anything longer is cut off. It limits the size of *one chunk*, not the size of a PDF |
| **Chunk** | A piece of a document that **we** cut (about 350 tokens) | Each chunk gets its own vector. A 5-page and a 500-page PDF are handled the same way, just with more chunks |
| **Overlap** | The last ~50 tokens of a chunk repeated at the start of the next | Prevents a sentence or idea from being cut in half at a boundary |
| **Prompt prefix (for embeddings)** | A short label added before the text telling the model whether it is a *question* or a *document* | EmbeddingGemma retrieves better when queries and documents are marked correctly |
| **Cosine similarity** | A score for how close two vectors are (closer to 1 = more similar) | How we rank chunks against a question |
| **top_k** | How many of the closest chunks we fetch (5 to 6 for us) | Those chunks become the context sent to the LLM |
| **Matryoshka (MRL)** | A trick that lets you cut a vector shorter (768 → 512) with a small quality loss | An optional storage-saving lever later |
| **Quantization** | Storing the model's numbers with fewer bits to save RAM | Not used in V1 (we keep full precision for simplicity) |
| **RAM vs. storage** | RAM = memory used while the program runs; storage = disk space | The embedding model lives in RAM; vectors live on disk. RAM is what costs us in the cloud |
| **MTEB** | A public benchmark that scores embedding models across many tasks | A rough guide only; our own eval set (Phase 5) is what really matters |

---

## Target architecture (V1)

```text
                        ┌──────────────────────────────┐
  Streamlit UI ───────▶ │        FastAPI backend       │
  (or /docs)            │  /documents  /ask  /health   │
                        └───┬───────────┬───────────┬──┘
                            │           │           │
                    raw PDF │   metadata│   vectors │ question + retrieved chunks
                            ▼           ▼           ▼
                      ┌─────────┐  ┌──────────────────────┐   ┌──────────────┐
                      │ S3/MinIO│  │ PostgreSQL + pgvector│   │ Gemini Flash-│
                      └────▲────┘  └──────────▲───────────┘   │ Lite (API)   │
                           │                  │               └──────────────┘
                     ┌─────┴──────────────────┴─────┐
                     │ Ingestion pipeline           │
                     │ extract → clean → chunk →    │
                     │ embed (EmbeddingGemma, local)│
                     │ → store                      │
                     │ (plain Python, later wrapped │
                     │  by an Airflow DAG)          │
                     └──────────────────────────────┘
```

---

## Target repository structure

```text
enterprise-doc-intelligence/
├── app/
│   ├── api/              # FastAPI routers (documents, ask, health)
│   ├── core/             # config, logging, exceptions
│   ├── db/               # SQLAlchemy models, session, repositories
│   ├── services/         # storage, embeddings, llm, retrieval, rag
│   ├── pipeline/         # extract, clean, chunk, ingest (pure Python, no FastAPI imports)
│   └── schemas/          # Pydantic request/response models
├── airflow/dags/         # Phase 7
├── ui/                   # Streamlit app (Phase 8)
├── migrations/           # Alembic
├── tests/                # unit + integration
├── data/sample_docs/     # small non-sensitive test PDFs
├── data/eval/            # evaluation questions (Phase 5)
├── scripts/              # dev helpers, eval scripts, reembed
├── docker/               # Dockerfiles
├── docs/                 # architecture notes, diagrams, eval results, provider limits
├── .env.example
├── docker-compose.yml
├── Makefile
├── pyproject.toml
├── PROJECT.md
├── ROADMAP.md
└── README.md
```

**Design rule:** `pipeline/` and `services/` never import from `api/`. The pipeline must be runnable from a script, a test, FastAPI, or Airflow without changes.

---

## Owner environment notes (recorded 2026-10-02)

- **OS:** Windows. Commands and scripts in this project must work in PowerShell/Windows (not only Linux shells).
- **Project location:** `D:\Backup\School\Project\enterprise-doc-intelligence`
- **Installed:** Git, Python 3.12.14 (via `uv`; 3.14 also exists globally), `uv` 0.12.21, Docker 29.8.1 + Compose v5.5.1 (Docker disk image on D:), VS Code 1.139.1 (Python, Ruff, Docker extensions), PostgreSQL 18.3 + pgAdmin (`psql` on PATH).
- **Hardware:** 16 GB RAM; C: about 18 GB free; D: about 368 GB free.
- **Consequences to keep in mind:**
  1. **Port clash:** the local PostgreSQL 18 service normally uses port 5432, so the Docker Postgres uses host port **5433**.
  2. **C: is tight:** the Hugging Face cache (about 1.2 GB), PyTorch and package caches default to C:. If space gets low, move them to D: (for example by setting `HF_HOME` to a folder on D:).
  3. **`make` on Windows** may be missing (see 0.6).
  4. **GitHub auth** is a fine-grained token (HTTPS). PRs can be created from the GitHub web page. Never paste tokens or API keys into chat, and never commit them.
- **Gemini free-tier limits (read from the owner's AI Studio console):** `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` both 15 requests/min, 250K tokens/min, 500 requests/day. This matches the third-party measurement in D2. Re-check at the start of Phase 6.
- **Owner working preference:** one step at a time, concise practical instructions, and the owner confirms each result before the next step.

---

# PHASES

---

## Phase 0: Environment preparation 🟨

**Goal:** A clean, reproducible, safe workspace so that later phases never stall on tooling problems.
**Why it matters:** Most "senior" habits (pinned versions, secrets hygiene, one-command setup) are cheap now and painful to add later.

### 0.1 Local machine ✅
- [x] Install Git and configure `user.name` / `user.email`
- [x] Install Python 3.12 (via `uv` or `pyenv`) (3.12.14 via `uv`; Python 3.14 also exists globally, so always pin 3.12 explicitly)
- [x] Install `uv`
- [x] Install Docker Desktop (or Docker Engine) and verify `docker run hello-world`
- [x] Install Docker Compose (bundled with Docker Desktop) and verify `docker compose version`
- [x] Install an editor with Python support (VS Code + Python, Ruff, Docker extensions)
- [x] Install a DB client (DBeaver or `psql`) to inspect Postgres (PostgreSQL 18.3 + pgAdmin installed locally, `psql` on PATH)
- [x] Check free disk space and RAM (16 GB RAM; C: about 18 GB free; D: about 368 GB free; Docker disk image is on D:)
- [x] ~~Install AWS CLI v2~~ → moved to Phase 11 (see decision D3)

### 0.2 Accounts and keys ✅
- [x] GitHub account + HTTPS authentication with a fine-grained Personal Access Token (Contents: read and write). SSH not used
- [x] **AWS account: deliberately NOT created yet (still the plan).** New accounts get a credit plan lasting about 6 months from signup, so we open it right before Phase 11 (see D3). Phases 0 to 10 run fully local (MinIO replaces S3). The AWS safety checklist (MFA, IAM user, budget alert) lives in Phase 11.
- [x] **Hugging Face account**, open the EmbeddingGemma page, **accept the Gemma license**, and create a **read-only access token**. Put it in `.env` as `HF_TOKEN` (never in git)
- [x] Download the model once and run a tiny test: embed one question and one sentence, confirm the vector has **768 numbers** (done: both gave 768; the model is in the Hugging Face cache, outside the project)
- [x] Create a Google AI Studio API key (Gemini) and put it in `.env` (never in git)
- [x] Find your **real free-tier limits** for `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` in the AI Studio rate-limit console. Result: **both 15 requests/min, 250K tokens/min, 500 requests/day**
- [ ] Write those limits in `docs/provider_limits.md` with the date (draft file prepared; add it to the repo when `docs/` gets its first real file)
- [x] Verify the model names exist for your key (a one-line test call for each); if a name is unavailable, record the closest Flash-Lite model that works (both names work)
- [ ] (Optional, later) Install Ollama if you ever want a local/offline LLM. Not required for V1

### 0.3 Repository ✅
- [x] Create the GitHub repo `enterprise-doc-intelligence` (private at first)
- [x] Add the target folder structure (including `tests/unit` and `tests/integration`). **Decision: no `.gitkeep` files.** Git doesn't track empty folders, so each folder appears in the repo when its first real file is added
- [x] Add `PROJECT.md` and `ROADMAP.md` (see the changelog: these two files were rewritten afterwards, so the repo copies must be refreshed)
- [x] Create a proper `.gitignore` (Python, `.env`, `data/` private files, `.venv`, IDE files, model caches)
- [x] Create `.env.example` (all variable names, **no real secrets**) and a local `.env` (git-ignored)
- [x] Choose a branching habit: `main` is always working; work on `feature/...` branches and merge via PR (even solo). No feature branch is created until real feature work starts
- [x] Adopt **Conventional Commits** (`feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`). First commit: `chore: initialize project repository`, pushed to `origin/main`, working tree clean

### 0.4 Python project setup
- [ ] `uv init` and create `pyproject.toml` (a `pyproject.toml` placeholder already exists from 0.3: review it and complete it, don't overwrite blindly)
- [ ] Pin the Python version (`.python-version`) to **3.12** (3.14 also exists on this machine, so be explicit)
- [ ] Add initial dependencies: `fastapi`, `uvicorn`, `pydantic-settings`, `sqlalchemy`, `alembic`, `psycopg`, `boto3`
- [ ] Add dev dependencies: `pytest`, `pytest-cov`, `httpx`, `ruff`, `pre-commit`
- [ ] Configure `ruff` in `pyproject.toml`
- [ ] Set up `pre-commit` (ruff, trailing whitespace, detect-secrets or `gitleaks`)
- [ ] *(Deferred to Phase 4)* `sentence-transformers` and the Gemini SDK are added when first needed; PyTorch is large, so we don't pull it in before then (the Phase 0 model test can use a throwaway virtual environment)

### 0.5 Local infrastructure with Docker Compose
- [ ] `docker-compose.yml` with **PostgreSQL + pgvector** (image `pgvector/pgvector`)
- [ ] **Map the Docker Postgres to host port 5433** (not 5432): PostgreSQL 18 is also installed locally on this machine and normally uses 5432, which would clash. `DATABASE_URL` must use the chosen port
- [ ] Add **MinIO** (local S3) with a persistent volume
- [ ] Named volumes for persistence
- [ ] Health checks for each service
- [ ] Verify: connect to Postgres with the DB client and run `CREATE EXTENSION vector;`
- [ ] Verify: open the MinIO console and create a bucket
- [ ] Verify: upload and download a file to MinIO via `boto3` using the S3 API

### 0.6 Developer experience
- [ ] `Makefile` with: `make up`, `make down`, `make test`, `make lint`, `make fmt`, `make run`. **Windows note:** `make` is not installed by default; first check it works in your terminal, otherwise choose an equivalent (for example `just` or small PowerShell scripts) and keep the same command names
- [ ] Minimal GitHub Actions workflow: install deps → `ruff` → `pytest` (CI never downloads the real embedding model or calls the real LLM). **Note:** pushing workflow files with a fine-grained token needs its *Workflows: read and write* permission
- [ ] Collect 3 to 5 **sample PDFs** (public/non-sensitive: a public HR policy template, a technical doc, a short report) in `data/sample_docs/`. Include at least one multi-page, one with tables, **one French (or Arabic) PDF to verify multilingual retrieval**, and ideally one scanned/image-only PDF to test a known limitation.

### ✅ Definition of Done, Phase 0
- `git clone` + `cp .env.example .env` + `make up` gives a working Postgres (with pgvector) and MinIO on a fresh machine
- `make lint` and `make test` run (even with a single dummy test) locally and in CI
- EmbeddingGemma downloads with your Hugging Face token and produces 768-number vectors
- The Gemini API key works (a one-line test call succeeds) and real limits are recorded in `docs/provider_limits.md`
- Sample PDFs are in place
- Tag: `phase-0-done`

---

## Phase 1: Project skeleton and FastAPI foundation ⬜

**Goal:** A well-structured, running API that other phases plug into.

### Tasks
- [ ] `app/main.py` with the FastAPI app factory
- [ ] Central config with `pydantic-settings` (all settings from environment variables, typed), including: `EMBEDDING_MODEL=google/embeddinggemma-300m`, `EMBEDDING_DIM=768`, `HF_TOKEN`, `CHUNK_TARGET_TOKENS=350`, `CHUNK_OVERLAP_TOKENS=50`, `CHUNK_MAX_TOKENS=512`, `LLM_PROVIDER`, `LLM_MODEL=gemini-3.5-flash-lite`, `LLM_FALLBACK_MODEL=gemini-3.1-flash-lite`, `GEMINI_API_KEY`
- [ ] Structured logging (simple JSON or key=value logs, with request IDs if easy)
- [ ] `GET /health` (API up) and `GET /health/ready` (checks DB and storage connectivity)
- [ ] Global exception handling: consistent error JSON format
- [ ] API versioning prefix (`/api/v1`)
- [ ] First tests: health endpoint via `TestClient`
- [ ] Verify the auto-generated docs at `/docs`

### ✅ Definition of Done
- `make run` starts the API; `/docs` loads; `/health/ready` reports DB and storage status
- Tests pass in CI
- No secrets in the repo; all config comes from env
- Tag: `phase-1-done`

---

## Phase 2: Storage and database layer ⬜

**Goal:** Users can upload a PDF; it is safely stored and tracked.

### Data model (initial)
- `documents`: id, filename, title (optional, used as the document title when embedding), content_type, size_bytes, s3_key, checksum (sha256), status (`uploaded`/`processing`/`processed`/`failed`), error_message, page_count, created_at, updated_at
- `chunks`: id, document_id (FK), chunk_index, page_number, text, token_count, embedding `vector(768)` (added in Phase 4), embedding_model (added in Phase 4), created_at
- (Optional) `ingestion_runs`: document_id, started_at, finished_at, status, error. Only if it helps Phase 7.

### Tasks
- [ ] SQLAlchemy models and Alembic initial migration
- [ ] DB session management (dependency injection in FastAPI)
- [ ] Repository layer for documents (keeps SQL out of endpoints)
- [ ] `StorageService` (S3 interface: `upload`, `download`, `delete`, `exists`). Works with MinIO locally and S3 in the cloud through an endpoint-URL setting
- [ ] `POST /api/v1/documents`: validate (PDF only, max size), compute checksum, store in S3, insert the metadata row
- [ ] Duplicate detection by checksum (return the existing document instead of re-uploading)
- [ ] `GET /api/v1/documents` and `GET /api/v1/documents/{id}`
- [ ] `DELETE /api/v1/documents/{id}` (removes the S3 object and DB rows)
- [ ] Safe S3 key scheme (e.g. `documents/{uuid}/original.pdf`, never trust the user filename as a path)
- [ ] Tests: upload valid PDF, reject non-PDF, reject oversized file, duplicate handling

### ✅ Definition of Done
- Upload via `/docs` → object visible in MinIO, row visible in Postgres
- Invalid uploads fail with clear error messages
- Migrations apply cleanly on an empty DB (`alembic upgrade head`)
- Tag: `phase-2-done`

---

## Phase 3: Document processing (extract, clean, chunk) ⬜

**Goal:** Turn a PDF into clean, **page-aware** text chunks of a good size for EmbeddingGemma. This is where RAG quality is mostly decided.

### Tasks
- [ ] `extract.py`: PyMuPDF, returns text **per page** (keep page numbers!)
- [ ] Detect pages with little or no text (likely scanned) and flag them. **OCR is out of scope for V1**; fail gracefully with a clear message/warning
- [ ] `clean.py`: normalize whitespace, fix hyphenated line breaks, remove repeated headers/footers (simple heuristics), strip control characters
- [ ] `chunk.py`: chunking with **configurable size and overlap**. Defaults: **target about 350 tokens, overlap about 50 tokens, hard maximum 512** (far below the model's 2,048 limit on purpose: focused chunks retrieve better). Count tokens with the **EmbeddingGemma tokenizer**, not word counts. Respect paragraph/sentence boundaries where possible
- [ ] Each chunk carries: document_id, page_number (or page range), chunk_index, text, token_count
- [ ] `ingest.py`: orchestrates extract → clean → chunk as plain functions (no FastAPI imports)
- [ ] Store chunks in Postgres; update document status and page_count
- [ ] Script `scripts/inspect_chunks.py` to eyeball the chunks for a document (look at them with your own eyes; this finds 80% of the quality problems)
- [ ] Unit tests on small fixtures: cleaning edge cases, chunk sizes, overlap, page mapping, and a test that no chunk exceeds the configured hard maximum

### ✅ Definition of Done
- Processing the sample PDFs produces sensible chunks with correct page numbers
- No chunk exceeds the hard maximum
- Re-processing a document is **idempotent** (old chunks replaced, no duplicates)
- Failures set `status=failed` with an `error_message`
- Tag: `phase-3-done`

---

## Phase 4: Embeddings and vector store ⬜

**Goal:** Every chunk gets a vector, stored and searchable.

### Tasks
- [ ] Add `sentence-transformers` (CPU-only PyTorch build, to keep installs and images smaller)
- [ ] `EmbeddingService` interface (`embed_documents(list[str], titles)`, `embed_query(str)`, plus `model_name` and `dimension` properties)
- [ ] `EmbeddingGemmaService`: load `google/embeddinggemma-300m` **once** (lazy singleton, warm-up at startup) in **float32**; use `encode_document` for chunks (with the document title) and `encode_query` for questions; encode in **batches**; use **cosine** distance
- [ ] Alembic migration: add `embedding vector(768)` and `embedding_model` to `chunks`
- [ ] Startup check: configured `EMBEDDING_DIM` must match the model's real dimension and the DB column, otherwise fail fast with a clear error
- [ ] Vector index: start with exact search; add an HNSW index with cosine distance when data grows
- [ ] Extend `ingest.py`: … → chunk → embed → store vectors (with `embedding_model` recorded)
- [ ] Measure and log embedding speed (chunks per second) and the process's memory use
- [ ] `scripts/reembed.py`: re-embed all chunks with the currently configured model (kept for any future model change; vectors from different models must never be mixed)
- [ ] Tests with a **fake embedding service** (deterministic, no model download) so CI stays fast; one slower test with the real model, marked separately and skipped in CI

### ✅ Definition of Done
- After ingesting the sample PDFs, every chunk has an embedding
- A raw SQL similarity query returns sensible neighbors for a test string
- Embedding speed and memory use are recorded in `docs/eval_results.md`
- Tag: `phase-4-done`

---

## Phase 5: Retrieval ⬜

**Goal:** Given a question, return the right chunks. **Validate retrieval before adding the LLM.** The model is already decided; this phase checks that our *pipeline settings* work on your documents.

### Tasks
- [ ] `RetrievalService.search(query, top_k, document_ids=None)` (default `top_k` about 5 to 6)
- [ ] Return chunk text, score, document name, page number
- [ ] Optional filter by document(s)
- [ ] Optional minimum similarity threshold (to avoid returning junk; calibrate it on real scores, don't guess)
- [ ] `POST /api/v1/search` (debug/inspection endpoint, useful forever)
- [ ] **Mini evaluation set:** 15 to 25 questions over the sample docs (including at least a few in French/Arabic if you have such a PDF), each with the expected document/page. Stored in `data/eval/questions.json`
- [ ] `scripts/eval_retrieval.py`: reports **hit rate@k** (was the right page in the top-k?)
- [ ] Tune **chunk size, overlap, top_k and the similarity threshold** using the eval set (these settings, not the model, are what we adjust). Record results in `docs/eval_results.md`

### ✅ Definition of Done
- The eval script runs with one command and prints hit rate@k
- Baseline results are documented (even if mediocre, that is honest data to improve from)
- Tag: `phase-5-done`

---

## Phase 6: Generation (RAG) and citations ⬜

**Goal:** Grounded answers with sources, and honesty when the answer isn't in the documents.

### Tasks
- [ ] Re-verify the model names (`gemini-3.5-flash-lite` primary, `gemini-3.1-flash-lite` backup) and your real limits in the AI Studio console before writing code
- [ ] `LLMService` interface (`generate(messages) -> text`) with a Gemini implementation (OpenAI-compatible endpoint first; official `google-genai` SDK if needed). Model names come from config
- [ ] **Quota-aware behavior:** timeouts generous enough for a free tier (measure real latency and record it), retries with exponential backoff on 429/5xx, automatic switch to the backup model, and a clear typed error when the **daily quota is exhausted** (the UI shows a friendly message)
- [ ] Prompt template in a dedicated file (versioned in git), with rules:
  - answer **only** from the provided context
  - say clearly when the context does not contain the answer
  - cite sources by document and page
- [ ] Context builder: assemble the top-k chunks with clear source labels, and respect a **token budget** (truncate or drop the lowest-ranked chunks)
- [ ] `POST /api/v1/ask` → `{ answer, sources: [{document, page, chunk_id, snippet, score}] }`
- [ ] Handle the "no relevant chunks found" case **without calling the LLM** (saves quota)
- [ ] Basic protection against prompt injection from documents: treat retrieved text as data, say so in the system prompt
- [ ] Log per request: question, retrieved chunk IDs, latency, token usage, and a **running count of real LLM calls per day** (so we never burn the free daily quota by accident)
- [ ] Tests: RAG flow with fake embeddings + **fake LLM** (automated tests never call the real API); a handful of manual end-to-end tests with the real LLM
- [ ] Try 10 to 15 "hard" questions: unanswerable ones, ambiguous ones, multi-page ones. Note the failures in `docs/known_limitations.md`

### ✅ Definition of Done
- `/ask` returns an answer with correct page citations for questions in the sample docs
- Unanswerable questions get an honest "not found in the documents" answer
- Hitting the daily quota produces a clear error, not a crash
- Tag: `phase-6-done` (**the core V1 loop is complete here**)

---

## Phase 7: Orchestration with Airflow ⬜

**Goal:** Run ingestion as a visible, retryable workflow instead of a function call. Only now, because the pipeline already works.

### Tasks
- [ ] Add Airflow to Docker Compose (keep it minimal: LocalExecutor, its own metadata DB or schema, **not** your app DB)
- [ ] DAG `ingest_document` with tasks mirroring the pipeline: `extract → clean → chunk → embed → store`, each calling the **existing** `pipeline/` functions
- [ ] Make sure the embedding model is available to the Airflow worker (shared image/dependencies or a mounted model cache) without downloading it on every run
- [ ] Trigger: on upload, the API triggers the DAG via the Airflow REST API (passing `document_id`)
- [ ] Update document status from the DAG (`processing` → `processed`/`failed`)
- [ ] Retries and failure handling configured per task
- [ ] `GET /api/v1/documents/{id}` shows the current processing status
- [ ] Fallback: a config flag to run ingestion synchronously (useful for tests, quick local runs, and possibly the cloud)

> **Checkpoint:** If Airflow turns out to cost too much time or memory for what it adds, discuss switching this phase to FastAPI `BackgroundTasks` and note it in the decision log. Honest engineering trade-offs are a good thing to show.

### ✅ Definition of Done
- Upload → DAG run visible in the Airflow UI → document becomes `processed` → `/ask` works on it
- A deliberately broken PDF results in a `failed` run with a readable error
- Tag: `phase-7-done`

---

## Phase 8: Demo UI (Streamlit) ⬜

**Goal:** A product anyone can use in 2 minutes, which is also your best demo for recruiters.
**Design rule:** the UI talks **only to the public API** (never the DB or S3 directly), so a future React frontend can replace it without backend changes.

### Tasks
- [ ] `ui/` Streamlit app with a thin API client module (base URL from env)
- [ ] **Documents page:** upload a PDF, list documents with status (`uploaded` / `processing` / `processed` / `failed`), delete a document
- [ ] **Chat page:** ask a question, show the answer, show **sources** (document name, page, snippet) in expandable blocks
- [ ] Optional filter: ask only within selected documents
- [ ] Friendly loading states (the free LLM tier can be slow), clear error messages (API down, file rejected, "not found in documents", **daily AI quota reached**)
- [ ] Keep the session's chat history in Streamlit state (no DB persistence in V1)
- [ ] Add the UI as a service in Docker Compose (finalized in Phase 10)

### ✅ Definition of Done
- A non-technical person can upload a PDF, wait for `processed`, ask a question, and see cited sources without ever touching `/docs`
- Tag: `phase-8-done`

---

## Phase 9: Hardening: tests, errors, quality ⬜

**Goal:** Turn "works on my machine" into "reliable".

### Tasks
- [ ] Test coverage review: unit tests for pipeline and services, integration tests for the API with a test DB
- [ ] Integration test for the whole flow on a small PDF (upload → process → ask), using fake LLM/embeddings in CI
- [ ] Edge cases: empty PDF, password-protected PDF, corrupt file, very large file, **French/Arabic PDF (confirm multilingual retrieval works, record the results)**, scanned PDF
- [ ] Input validation and size/timeouts limits reviewed
- [ ] Secrets review: nothing committed, `.env.example` complete
- [ ] Basic API protection: a simple API key header (nothing more complex in V1)
- [ ] Dependency lock file up to date; `ruff` clean; CI green
- [ ] Re-run the eval set and record the final numbers

### ✅ Definition of Done
- CI is green on `main`; the main flow has an automated test
- Known limitations are written down honestly
- Tag: `phase-9-done`

---

## Phase 10: Full Dockerization ⬜

**Goal:** One command starts the complete system.

### Tasks
- [ ] Multi-stage `Dockerfile` for the API (small image, non-root user, pinned base image, **CPU-only PyTorch**)
- [ ] **Bake the EmbeddingGemma model into the image (or a cached volume)** so containers never download it at startup. The Hugging Face token is passed as a **build secret** and must not remain in the image layers
- [ ] `.dockerignore`
- [ ] Compose file includes: api, ui, postgres (pgvector), minio, airflow
- [ ] Config purely via environment variables; separate `docker-compose.override.yml` for dev conveniences
- [ ] Health checks and `depends_on` with health conditions
- [ ] Migrations run automatically (or via a documented one-shot command) at startup
- [ ] Verify from scratch: delete volumes → `docker compose up --build` → full flow works
- [ ] **Measure memory:** run the full flow and record `docker stats` (per container and total, with and without Airflow) in `docs/deployment.md`. This number decides the EC2 instance size in Phase 11

### ✅ Definition of Done
- A fresh clone + `.env` + one command = working system
- Memory footprint is measured and documented
- Tag: `phase-10-done`

---

## Phase 11: Deploy to AWS ⬜

**Goal:** The application is reachable online, with cost under control.
**Principle:** the cloud runs **only what the live product needs**. Dev tools and one-off jobs stay local.

### Decided path (see D3)
- **One EC2 instance** running the Docker Compose stack: **api, ui, postgres + pgvector** (the API also holds the embedding model in memory, because every question must be embedded at answer time)
- **Postgres in Docker on the instance** (data on an EBS volume) + nightly `pg_dump` to S3. RDS is the documented upgrade path, not V1
- **Real S3 bucket** (private, encryption on, public access blocked) instead of MinIO
- **IAM role** attached to the EC2 instance for S3 access (no access keys on the server)
- Security group: only ports 80/443 (and SSH from your IP only)
- Reverse proxy (Nginx or Caddy) + HTTPS if you have a domain (optional)

### OPEN DECISION: how documents get ingested in the cloud (decide at the start of this phase)
We deliberately leave this open until we see how the pipeline behaves in practice. Note that ingestion happens **every time a document is uploaded**, not once, so *something* must do that work if the cloud app accepts uploads. Options:
- **A) Full stack in the cloud, Airflow included.** Most realistic, needs the most RAM (bigger instance, more credits)
- **B) No Airflow in the cloud:** the cloud app ingests uploads with the synchronous/background mode built in Phase 7. Cheaper, still supports uploads
- **C) Read-only cloud demo:** ingest documents **locally** (with Airflow), copy the resulting Postgres data and PDFs to the cloud, and disable uploads there. Cheapest and simplest; the cloud only answers questions. (The embedding model is still needed there to embed questions.)

Use the memory numbers measured in Phase 10 plus your goals for the demo, then record the choice in the decision log.

### Tasks
**AWS account setup (done now, not earlier, because the credit clock starts at signup):**
- [ ] Create the AWS account, choose the **Free plan**, and note the creation date and credit expiry in the changelog
- [ ] Enable MFA on the root account, then **stop using root**
- [ ] Create an IAM user (or IAM Identity Center user) with least-privilege access for this project
- [ ] Create an **AWS Budget + billing alert** (also counts toward the onboarding credits)
- [ ] Choose one region and stick to it (e.g. `eu-west-3` Paris or `eu-west-1` Ireland)
- [ ] Install AWS CLI v2, run `aws configure`, verify with `aws sts get-caller-identity`

**Deployment:**
- [ ] Create the S3 bucket (private) and a least-privilege IAM policy/role
- [ ] Launch EC2, install Docker, pull the repo or images
- [ ] Production `.env` (secrets not in git; use SSM Parameter Store if comfortable, otherwise a server-only `.env`)
- [ ] Start the stack, run migrations, smoke-test upload (or pre-loaded data for option C) + ask
- [ ] Set up a CloudWatch billing alarm review; **stop the instance when not demoing**
- [ ] Document the deployment steps in `docs/deployment.md` so they're repeatable
- [ ] Optional: a simple GitHub Actions deploy step (only if time allows)

### ✅ Definition of Done
- The public URL can answer a question about a document (and accept an upload too, unless option C was chosen)
- Deployment steps are documented; cost is known and monitored
- Tag: `phase-11-done`

---

## Phase 12: Documentation and portfolio polish ⬜

**Goal:** Make the work legible to a recruiter or interviewer in 5 minutes.

### Tasks
- [ ] `README.md`: what it is, architecture diagram, tech stack and *why*, quickstart, example requests/responses
- [ ] Architecture diagram exported as an image in `docs/`
- [ ] Short demo (GIF or 2-minute video) of upload → ask → cited answer
- [ ] `docs/known_limitations.md` and `docs/eval_results.md` (shows engineering honesty)
- [ ] `docs/decisions.md` (why EmbeddingGemma and what it costs in RAM, why Gemini Flash-Lite, why pgvector, why these chunk sizes, why Airflow or not)
- [ ] "What I'd do in V2" section (stronger/larger embedding model, hybrid search, reranking, OCR, auth, observability), which **shows** you know the next steps without building them
- [ ] Clean the git history and tags; make the repo public if appropriate (no secrets, no private docs, no model weights!)
- [ ] Prepare a 2-minute verbal pitch of the project (problem → architecture → trade-offs → results)

### ✅ Definition of Done
- Someone who has never seen the project can understand, run, and judge it from the README alone
- Tag: `v1.0.0`

---

# V1 FINAL CHECKLIST (exit criteria)

- [ ] PDF upload works, stored in S3, metadata in Postgres
- [ ] Extraction → cleaning → chunking → embedding → vector storage works end to end
- [ ] `/ask` returns grounded answers with document/page citations
- [ ] Unanswerable questions are handled honestly; daily-quota errors are handled gracefully
- [ ] Ingestion orchestrated (Airflow, or a documented justified alternative)
- [ ] Streamlit UI lets a non-technical user upload, track status, ask, and see sources
- [ ] Tests + CI green; retrieval eval documented
- [ ] Full stack runs via Docker Compose
- [ ] Deployed on AWS and cost-controlled
- [ ] README, diagram, limitations, and decisions documented

---

# Future versions (NOT built in V1)

This section exists so V1 is designed to grow, without building any of it now. The right column is the **cheap hook we keep in V1** so the upgrade is painless.

## V2 candidates

| Improvement | Why | Hook already in V1 |
|-------------|-----|--------------------|
| Stronger/larger embedding model (for example on a GPU or bigger server) | Higher retrieval quality | `EmbeddingService` interface, `embedding_model` column, `reembed.py`, eval set to prove the gain |
| Hybrid search (keyword/BM25 + vectors) and a reranker | Big retrieval-quality gain, especially for exact terms and numbers | Retrieval is isolated in `RetrievalService`; Postgres can do full-text search too |
| Paid/higher-quota LLM tier or a stronger model | Free tier caps requests and may use inputs to improve products | `LLMService` interface; model names come from config |
| Larger "parent" context around each retrieved chunk | Small chunks give the LLM limited context | Chunks store page and index, so neighbors are easy to fetch |
| OCR for scanned PDFs | V1 only flags image-only pages | Extraction flags low-text pages per page |
| Authentication, users, per-user document access | V1 has only a simple API key | `/api/v1` prefix and repository layer keep auth addable without rewrites |
| Conversation memory / follow-up questions | V1 is single-turn | `/ask` schema can accept an optional history later |
| Streaming answers | Better UX | `LLMService` interface can gain a streaming method |
| Automated RAG evaluation (faithfulness, answer quality) | V1 only measures retrieval hit rate | Eval set and scripts already exist |
| More file types (DOCX, HTML, TXT) | Broader usefulness | Extraction is a separate module per format |
| React frontend | Production-grade UI | UI only uses the public API |
| RDS instead of Postgres-on-EC2 | Managed backups, failover | Only `DATABASE_URL` changes; pgvector is supported |
| CI/CD auto-deploy, basic monitoring/alerts | Less manual work | CI already runs lint + tests |

## V3 candidates
Multi-tenant organizations, agentic workflows, infrastructure-as-code (Terraform), container orchestration, advanced observability, evaluation dashboards, fine-tuning/reranker training. **Only when a real problem demands them.**

---

# Working agreements

1. **One phase at a time.** No jumping ahead; no V2 features.
2. **Inspect the data at every stage** (raw text, chunks, retrieved chunks, final prompt). RAG bugs hide in the data, not the code.
3. **Interfaces around external services** (storage, embeddings, LLM) so they can be faked in tests and swapped later.
4. **Small commits, green `main`.**
5. **Write down decisions and limitations as we go** (future-you and interviewers will thank you).
6. **Protect the free quotas.** Automated tests never call the real LLM; count real calls; public sample documents only.
7. **Watch the AWS bill.** Stop what you're not using.

---

# Changelog

| Date | Change |
|------|--------|
| 2026-09-30 | Roadmap created. Phase 0 started. |
| 2026-09-30 | Researched and resolved parking-lot decisions (D1 to D4). Postgres on EC2 (RDS = upgrade path). UI promoted to a committed phase (Streamlit). AWS account creation deferred to Phase 11 because the new-account credit plan lasts ~6 months from signup. Added a "Future versions" section with V1 hooks. |
| 2026-09-30 | Embeddings first set to `all-MiniLM-L6-v2`; LLM locked to Gemini Flash-Lite (`gemini-3.5-flash-lite`, backup `gemini-3.1-flash-lite`). Newer measurements show full Flash models at ~20 requests/day on free keys vs ~500/day for Flash-Lite, correcting my earlier "generous" description. Added quota-aware tasks. |
| 2026-10-01 | **Embeddings changed to `google/embeddinggemma-300m`** (768 dims, 2,048-token input, 100+ languages, ~1.25 GB RAM), verified on the official model card. Reason: MiniLM was English-only with a 256-token cap; EmbeddingGemma is the strongest option found that still fits a small CPU server. **No model-comparison step in Phase 5** (decision by the project owner: use the best fitting model directly). Changes: `vector(768)`, chunks ~350 tokens (hard max 512), `encode_query`/`encode_document` prompts with document title, Hugging Face account + license + token in Phase 0 (gated model), model baked into Docker image with a build secret, memory measured in Phase 10. Added a Learning glossary. Phase 11: Airflow-in-cloud stays an open decision, now with three options (A full, B no Airflow, C read-only demo). |
| 2026-10-01 | `PROJECT.md` rewritten to be **non-technical** (idea, purpose, scope, principles, future ideas). Technical content lives only in this file. |
| 2026-10-02 | **Phase 0.1, 0.2 and 0.3 completed** (machine, accounts and keys, repository). EmbeddingGemma downloaded and tested (768 dims). Both Gemini Flash-Lite models tested; real limits recorded (15 RPM / 250K TPM / 500 RPD). Repo created and first commit pushed. Decisions: HTTPS + fine-grained token (no SSH); no `.gitkeep` files. Added owner environment notes (Windows, port 5433 for Docker Postgres, C: space, `make` on Windows, workflow-file token permission). |

# Open questions / parking lot

**Resolved:**
- [x] Embeddings: `google/embeddinggemma-300m`, local, no comparison phase (D1)
- [x] LLM: Gemini Flash-Lite family, free tier (D2)
- [x] Postgres: in Docker on EC2 for V1, RDS as upgrade path (D3)
- [x] UI: yes, Streamlit, committed as Phase 8 (D4)
- [x] Language of documents: no longer a blocker, the model is multilingual
- [x] Your real Gemini free-tier limits: 15 RPM / 250K TPM / 500 RPD on both Flash-Lite models (recorded 2026-10-02)
- [x] Your OS, RAM, disk and installed tools: Windows, 16 GB RAM, see the environment notes

**Still open (each has a decision point):**
- [ ] **Airflow / ingestion in the cloud: option A, B or C** (start of Phase 11, using Phase 10 memory numbers and how the pipeline behaves in practice)
- [ ] Do we want a custom domain + HTTPS for the demo? (Phase 11, optional)
