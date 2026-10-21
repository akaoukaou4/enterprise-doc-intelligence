# DECISIONS

**Question this file answers:** why is the system the way it is?
**Not here:** how it works now (ARCHITECTURE), the plan (ROADMAP), how to run it (README).

## How to read and write this file

- One record per decision, numbered `D-nn`. Append new ones at the end. Never delete or rewrite an old one (settled records may be compressed, see below).
- **Status:** *Accepted*, *Revisit at Phase N* (accepted, with a known trigger to look again), or *Superseded by D-nn*. When a decision changes, add a new record that says "Supersedes D-nn", and change the old status. Link both ways. Then run the ripple check: fix every doc that mentions the old decision, in the same commit.
- New records use the shape **Decision**, **Why**, **Rejected**, **Revisit**. Evidence tables are at the end (E-1 to E-5).
- Volatile facts (model names, quotas, versions) are written here once, with the date they were checked.
- **Compressed records.** D-01 to D-42 were compressed on 2026-10-22 to meet the size budget (ENGINEERING_STANDARDS section 13). Meaning, numbers, statuses and revisit triggers are kept. The full text is in Git at the tag `decisions-before-compress`. D-43 and later keep their full shape.
- Section numbers of the very old file (for example "12.2") no longer exist. That file is in Git at the tag `docs-before-restructure`.

---

## Scope and architecture

- **D-01 · Product and V1 scope** (Accepted). A document-intelligence assistant: upload PDFs, ask questions, get grounded answers with page and section citations. V1 is the smallest end-to-end path. Risk classification, audit prioritization, agents, fine-tuning and advanced automation are deferred. Every technology passes the 5-question test (ENGINEERING_STANDARDS section 1).
- **D-02 · Modular monolith** (Accepted). One Python app with internal layers; PostgreSQL and MinIO as containers. No microservices, Kubernetes or Kafka. Revisit only on a measured requirement.
- **D-03 · Independent pipeline, two execution modes** (Accepted). `app/pipeline/` imports no FastAPI, Airflow or database code. Direct mode: scripts and tests. Orchestrated mode: Airflow runs the same code (Phase 8). Embedding and storing are services in `app/services/`, not pipeline.
- **D-04 · Deployment path** (Accepted; revisit at Phase 12). Docker Compose locally first. AWS only after the local system works (EC2, RDS PostgreSQL + pgvector, S3, IAM, CloudWatch). Terraform last. Same app, only configuration changes. Rejected: EKS, Lambda, ECS, OpenSearch, Redis, queues.

## AI and document processing

- **D-05 · Gemini for generation** (Accepted). The project integrates AI, it does not train or host large models. The model is one setting (D-28).
- **D-06 · EmbeddingGemma, local, one setting** (Accepted). `google/embeddinggemma-300m`, 768 dimensions, set by `EMBEDDING_MODEL_ID`, read by both the chunker tokenizer and the embedding service. The size is checked against the database column when the model loads. Runs on CPU and sends no document text out. The model is gated: accept the license and run `uv run hf auth login` once; deployments need `HF_TOKEN` or a pre-downloaded model volume; CI never needs it. Phase 7 gave no reason to change it (E-4).
- **D-07 · Dense retrieval first, evaluate before optimizing** (Accepted; revisit at Phase 14). pgvector cosine similarity. No hybrid search, reranking, query expansion, threshold, document filter or vector index until evaluation shows a need. Phase 7: the expected source was in the top 3 for all 47 answerable questions (E-4). Revisit only if a larger corpus changes this.
- **D-08 · Docling and HybridChunker** (Accepted). Structure-aware parsing suits enterprise documents; confirmed on two PDFs and the 14-document corpus (E-4). Revisit if a later corpus shows chunking hurts retrieval.
- **D-09 · Provenance is part of the data** (Accepted). `Chunk(text, page_numbers, heading)`. `page_numbers` is a list because chunks span pages. Only the nearest heading is kept (Docling reports every heading as level 1). The stored row adds `document_id` and `chunk_index`. The schema follows what Docling provides.
- **D-10 · Real output first; CPU PyTorch; caches on D:** (Accepted). Inspect real Docling output before writing pipeline code. CPU-only PyTorch from an explicit `pytorch-cpu` uv index (the GTX 1050 with 4 GB is too small, CUDA wheels add GB and CI would download them). `UV_CACHE_DIR` and `HF_HOME` on D: (C: is nearly full; uv hardlinks need one drive).
- **D-11 · Four cleaning rules, each backed by data** (Accepted). Drop table-of-contents chunks (label `document_index`), remove the license watermark line, strip `\x08` and the byte-order mark, drop chunks empty after cleaning. No minimum chunk size. The ISO PDF gave 156 chunks, 84 of them contents junk. Rejected: pattern-based contents detection, a length threshold. Limit: works only when Docling detects the contents page.
- **D-12 · Known pipeline limits accepted** (Accepted; Phase 7: no measurable harm). Not fixed: text and tables inside images are unreliable; some headings are wrong or missing; tables can lose their header row or split across chunks; rows without separator lines merge. 11 table questions: all retrieved in the top 5, answers correct except one partial (q26). Revisit if a later corpus has failing tables. Candidate fix, untested: HybridChunker `repeat_table_header`.
- **D-13 · Embed `title: <heading> | text: <chunk>`, built by our code** (Accepted; supersedes the Phase 3 plan to embed `chunker.contextualize(chunk)`). `build_document_text` in `app/services/embeddings.py` builds the model's native format from our `Chunk`. The model's own `encode_document` always writes `title: none`. Ours keeps `Chunk` unchanged and the embed stage independent of Docling; without a heading it equals the model's prompt (cosine 1.0000). Stored `text` stays plain. Not tested in Phase 7. Revisit if retrieval gets worse on a new corpus (heading versus `none`).
- **D-14 · 512-token chunks measured with the EmbeddingGemma tokenizer** (Accepted; supersedes the MiniLM tokenizer). The model accepts 2048 tokens; the budget is 512. Its larger vocabulary fits 30 to 60% more text (E-2); average chunk 170 to 290 tokens. 256 and 1024 were not tested. Revisit only if retrieval gets worse (`MAX_CHUNK_TOKENS`, re-ingest, re-evaluate).
- **D-15 · Third-party sample documents stay local** (Accepted; exception D-40). PDFs and Docling output stay in git-ignored folders. `data/eval/` is trackable (JSON or YAML; `.gitignore` ignores `data/**/*.csv`). The ISO/IEC 27001 standard is copyrighted: local use only, never sent to Gemini. The repository is public.

## Data, storage and backend

- **D-16 · PostgreSQL + pgvector, one table of chunks** (Accepted). `document_chunks`: `document_id` FK `ON DELETE CASCADE`, `chunk_index`, `text`, `page_numbers integer[]`, `heading`, `embedding vector(768) NOT NULL`, `UNIQUE (document_id, chunk_index)`. Similarity is `1 - cosine_distance` (vectors are normalized). No vector index (D-07). Rejected: a dedicated vector database. The migration was written by hand (autogenerate cannot create the extension); the secret scanner flagged its hex revision ids, fixed with an inline `# pragma: allowlist secret`.
- **D-17 · Object storage through boto3 and a small `StorageService`** (Accepted). Originals live under `documents/<document_id>/<filename>`, never in the database. boto3 talks to MinIO when `MINIO_ENDPOINT` is set, to real S3 otherwise (IAM role on EC2). The service has `upload`, `download`, `delete`, is the only importer of boto3, builds its client lazily and maps errors to `NotFoundError` or `ExternalServiceError`. `minio-init` creates the bucket. No interface class. Limits: files are bytes in memory (fine at 20 MB); a missing `.env` makes boto3 try real AWS; `MINIO_*` names may become `S3_*` in Phase 12.
- **D-18 · Alembic for every schema change** (Accepted). Migrations in `migrations/`, URL from `Settings`, `versions/` excluded from Ruff, every generated migration read before applying. No `create_all`.
- **D-19 · Upload rules and document model** (Accepted). Python-generated UUID, unique `storage_key` (never returned by the API), plain-string `status` (not an ENUM). Accept only `application/pdf` whose bytes start with `%PDF-`, not empty, within `MAX_UPLOAD_MB` (20). Filename reduced to its last path component. Order: validate, store the file, insert the row; if the insert fails, roll back and delete the file. Limit: a crash between the two steps can leave an orphan file; no cleanup job at this scale.
- **D-20 · Backend conventions** (Accepted). One typed `Settings` (pydantic-settings); settings are added only when a phase needs them. `create_app()` factory. Standard logging. One error shape `{"error": {"code", "message"}}` with `AppError` subclasses; unexpected exceptions return a generic message. Business endpoints under `/api/v1`, health endpoints unversioned. Thin routes, logic in services injected through `app/api/deps.py`. `DATABASE_URL` optional and the engine lazy with `pool_pre_ping` (CI runs without a database; the app recovers after a restart). Unit tests use `dependency_overrides`.
- **D-21 · EmbeddingService: lazy, shared, behind plain `def` routes** (Accepted; revisit at Phase 11). The model loads on first use, on CPU; one instance per process (`lru_cache` in `deps.py`). Search and ask routes are plain `def`, so blocking work runs in the thread pool. Costs: first request about 22 s (about 15 update checks to huggingface.co), no loading lock, `--reload` reloads the model. Phase 11: run offline with a pre-downloaded model; decide between preloading and lazy loading.
- **D-22 · ChunkService replaces in one transaction, validates first** (Accepted). `replace_chunks(document_id, chunks, vectors)` checks counts and 768 values (`ValueError`), raises `NotFoundError` for an unknown document, deletes old chunks and inserts new ones in one transaction, and keeps the old chunks on any failure. An empty list clears the chunks. It does not change `documents.status` (D-45).
- **D-23 · One ingestion code path** (Accepted). Phase 6: `scripts/ingest_document.py` chained download, `process_pdf`, `embed_documents`, `replace_chunks` with no class. Phase 7: the bulk script needed the same four calls, so they moved into `IngestionService` (a second caller appeared). Phase 8: both scripts go through `IngestionRunner` (D-45), which also sets the status. Airflow runs these same scripts (D-44).
- **D-24 · Retrieval returns plain objects; `/search` is an inspection endpoint** (Accepted). `RetrievalService.search` returns frozen `RetrievedChunk(document_id, filename, page_numbers, heading, text, similarity)`, with the file name joined in the query. Citations need no second lookup and callers never see ORM rows or vectors. `/search` shows whether retrieval or generation failed.
- **D-25 · Input limits and stable ordering** (Accepted; default `top_k` superseded by D-42). `top_k` 1 to 20; question stripped, 1 to 1000 characters. Constants in `retrieval.py`, imported by the schemas; API returns 422, the service raises `ValueError`. Order by distance, `document_id`, `chunk_index`, so tests and evaluation repeat. The numbers were guesses; the question length limit was never tested. Known gap: `ValueError` is not mapped to HTTP (backlog).
- **D-26 · Tests: fakes, hand-made vectors, skipped integration, unique names** (Accepted). Unit tests use fakes and run in CI. Integration tests use the real containers, skip themselves when unavailable and delete only what they created. Retrieval integration tests use hand-made vectors (similarity 1.0, 0.7071, 0.0). Test file names are unique across `tests/` (no `__init__.py`).

## Generation (Phase 6)

- **D-27 · Check changing facts in official documentation first** (Accepted). SDK shape, model names, quotas, data-use terms: use the official source, a small real call, or ask. The quotas seen in AI Studio differed from what was assumed and changed the model choice (D-28).
- **D-28 · Model `gemini-3.5-flash-lite`, set by `GEMINI_MODEL`** (Accepted; revisit before deployment). Key in `GEMINI_API_KEY` as a `SecretStr`. Checked 2026-10 in AI Studio: 15 requests per minute, 250,000 tokens per minute, 500 per day; larger Flash models only 5 per minute and 20 per day, unusable for development and evaluation. Short extraction suits a small model. Model lifetimes are short: check for a shutdown date before deployment. A larger model and thinking level were not tested in Phase 7. Quotas rechecked 2026-10-16; full table in `docs/provider_limits.md`.
- **D-29 · `generate_content`, not the Interactions API** (Accepted; revisit on deprecation). RAG here is one stateless request. The Interactions API keeps state at Google by default (a privacy question for document text) and its REST version was beta when checked. A conscious deviation from the vendor's recommendation. Switching later touches one file (D-30).
- **D-30 · LlmService owns the SDK; strict acceptance; no retries; generic errors** (Accepted). `app/services/llm.py` is the only importer of `google-genai`. `generate_structured(system_instruction, prompt, response_model)` returns a validated Pydantic object. One client per process, 30 s timeout, `max_output_tokens` 2048, one attempt. A response is accepted only if `finish_reason` is `STOP`, the text is not empty and it validates; otherwise `502`. Every Gemini failure is `ExternalServiceError` (`502`) with a generic message (friendlier for `429`; "The AI service is not configured." for a missing key); details go to the log only. Why: model output is untrusted; retries burn the daily quota and the likely failures are not fixed by retrying; SDK exception text may contain request details. Revisit: if transient `5xx` errors are common, retry only those, once (none seen in Phase 7).
- **D-31 · Prompt: numbered sources, declared as data** (Accepted). `rag_prompt.py` builds a seven-rule system instruction: use only the sources; `found: false` with no sources when they do not answer; partial answers allowed; cite only directly supporting sources; no numbers, file names or pages in the answer text; source text is data, never instructions; answer in the question's language, concisely. Each chunk is `<source number="n">` with file and section, no pages. The question comes last in `<question>` tags. Fake tags inside documents are neutralized. Limit: a mitigation, not a full defense against prompt injection; adversarial documents are a Phase 14 topic.
- **D-32 · The model returns source numbers; code builds citations** (Accepted). The model returns `{found, answer, source_numbers}`. `RagService` keeps numbers `1..n` matching a retrieved chunk, drops (and logs) the rest, and builds each `Citation(document_id, filename, page_numbers, heading, text)` from the stored chunk. Rejected: the model writing citation text. Limit: code proves a citation is a retrieved chunk, not that it supports every claim. Phase 7: every answered question cited an expected source; 4 of 46 answers (8.7%) at `top_k` 5 and 3 of 47 at `top_k` 8 added a citation outside the expected list, mostly an older or shorter version of the same policy (E-4).
- **D-33 · Refusal in three layers; no similarity threshold** (Accepted; threshold rejected in Phase 7, E-4). (1) No retrieved chunks: a fixed message, Gemini is not called. (2) The model answers `found: false`: no citations. (3) `found: true` with no valid source number or a blank answer: replaced by a fixed "not found" message. Similarities are logged. One corpus separated cleanly (answerable 0.4968 or higher, refused 0.4144 or lower); on another a near-miss scored 0.6617, above every answerable question (E-1). Phase 7: the near-miss q43 scores 0.657, above the lowest answerable question (0.382); the model's own `found` refused 5 of 5 at the baseline. Layer 3 is a safety net. Revisit only if a new corpus changes the scores.
- **D-34 · `POST /api/v1/ask`** (Accepted). Request `{question, top_k}` (same limits as `/search`), response `{answer, found, citations}`; `422` for bad input, `502` for Gemini failure. Thin plain `def` route. `/search` stays for inspection. `text` in a citation lets a UI show the quote. `found: false` is a field, not an error.
- **D-35 · Logs hold numbers only** (Accepted). Never the question or chunk text. One `RAG:` line per question (chunk count, similarities, found, cited and dropped numbers) and one `Gemini call:` line (model, latency, finish reason, token counts).
- **D-36 · Free-tier data use decides which documents go to Gemini** (Accepted; revisit at Phase 12). On the free tier only fictional, openly licensed or non-sensitive documents go through `/ask`. Ingestion, embeddings and `/search` run locally; only `/ask` calls Gemini and sends the retrieved chunks. Google's terms (checked 2026-10): free-tier prompts and responses may be used to improve its products; paid tier not. Phase 12: decide whether a paid key is needed for real company documents.
- **D-37 · Tests never call Gemini** (Accepted). Fake client for `LlmService`, plain chunks for the prompt, fake services for `RagService`, dependency overrides for the endpoint; the evaluation runner (D-41) the same. The one real call is `scripts/smoke_gemini.py`, run by hand with a fictional café. The secret scanner flagged a fake key in a test; fixed with an inline allow comment.
- **D-38 · Test corpus: fictional policy documents** (Accepted; supersedes the Docling Technical Report as corpus; location amended by D-40). Three fictional German-company policy PDFs first, eleven more ingested in Phase 7 (D-41). The Technical Report was deleted from the database (one `DELETE` naming its exact id; chunks cascade) and from MinIO; no delete endpoint was built for a one-off cleanup. Policies are what the product is for, they are fictional (so the free tier is safe), and several overlap on purpose (smoking) to test citation precision. Phase 3 to 5 measurements on the Technical Report stay valid as history.

## Process

- **D-39 · Documentation system** (Accepted, 2026-10-13). Four project docs, one question each: README (use), ROADMAP (plan and status, handoff block on top), ARCHITECTURE (the system today, with invariants), DECISIONS (why, append-only with status). PROJECT.md holds scope. One fact has one home. Working rules live in a private cross-project kit loaded through the Project instructions. End of each phase: ripple check, update the four docs as complete files, one commit, tag. Why: the old docs reached about 150 KB, copied facts across files and went stale. Rejected: one doc per phase, patch scripts.
- **D-40 · The fictional corpus is committed in `data/corpus/`** (Accepted, 2026-10-13; amends D-15 and D-38). The 14 policy PDFs of the fictional German company are tracked by Git; `.gitignore` ignores all other PDFs under `data/` and re-includes only `data/corpus/*.pdf`. `data/corpus/SOURCES.md` records the origin: generated by the repository owner with an AI assistant, fictional, no real or third-party content. Anyone who clones the repo can reproduce the Phase 7 evaluation. Revisit: if any file is not the owner's own generated content, remove it from the repo and from `SOURCES.md`.

## Evaluation (Phase 7)

- **D-41 · Evaluation design: separate retrieval and generation, correctness by hand** (Accepted, 2026-10-18). `data/eval/questions.json` version 5: 52 questions, 47 answerable and 5 to refuse. Kinds: overlap 16, single passage 13, table 11, multi-passage 3, cross-language 4 (German, French, Spanish), refusals (near-miss 3, not answerable 2). Answerable questions have expected facts (for hand review) and expected sources (file and pages; `any` or `all`). Retrieval is measured from one top-20 search per question (hit at 1, 3, 5, 10 and the answer size, MRR). Generation is measured separately (answered, refused, citations cover the expected sources, padding, precision). Correctness is read by hand. Contradictions inside the corpus are tests on purpose (alcohol rule, referral bonus, sidewalk smoking, strength of the harassment consequence). The runner calls the services directly, writes the result file after every question, waits 5 s between Gemini calls (12 a minute under the 15 limit) and stops after 3 failures in a row. Scoring is pure code in `app/evaluation/` (I12). Rejected: literal matching of expected facts (92 of them appear word for word in no chunk; 0 of 46 matched); grading with a second LLM; a refusal threshold (D-33). Limits: source matching is page-level (q07 counted a chunk on the right page that lacked the answer); a qualified answer (q16, q24) is judged by hand. Revisit: if the set grows or hand review is too slow, add short literal anchors per question.
- **D-42 · Default `top_k` is 8** (Accepted, 2026-10-18; supersedes the default of 5 in D-25). At 5, q07 (who is the Works Council chair) was refused: the contact tables of four files rank 6 to 9 (similarity 0.343 to 0.347, just below rank 5 at 0.351). At 8 it is answered correctly. Over 52 questions (E-4): answered 46/47 to 47/47, mean citation precision 0.969 to 0.979, padded answers 4/46 to 3/47, mean citations 1.67 to 1.72. q16 is flagged by the metric, but its answer is the accepted one. Cost: up to 8 chunks per prompt. Rejected: 10 (untested, more tokens); keeping 5 and merging contact chunks (a chunking change, re-ingest about 18 minutes). Revisit if token use or free-tier limits matter, or a larger corpus changes the picture.

---

## Orchestration (Phase 8)

### D-43 · Airflow 3.3.2, LocalExecutor, own compose in `airflow/` · Accepted (2026-10-18) · Revisit at Phase 12
**Decision.** Airflow 3.3.2 (the stable version in the official docs on 2026-10-18), run from `airflow/docker-compose.yaml`, separate from the root compose (`cd airflow; docker compose up -d`). Services: api-server, scheduler, dag-processor and its own `postgres:16` for metadata. LocalExecutor, `[core] parallelism` 2. DAGs are created paused, no examples, login `airflow` / `airflow` (local use only). Derived from the official compose; a header comment lists every change.
**Why.** Ingestion is one heavy task at a time (peak about 5.2 GB, E-5), so no Redis, worker or Flower, which saves memory on the 8 GB Docker VM. The root compose stays light for API work. Airflow's own metadata database means a reset cannot touch documents.
**Rejected.** CeleryExecutor (more containers, no gain). Airflow as a profile of the root compose (heavy image on every start). Airflow metadata in the application database (shared fate).
**Consequence.** Two compose files. The containers reach host services through `host.docker.internal` (PostgreSQL 5433, MinIO 9000); Phases 11 and 12 turn these into service names or RDS and S3. **Revisit** at Phase 12, or if ingestions must run in parallel.

### D-44 · The app runs in its own virtual environment in the Airflow image; the DAG calls the scripts · Accepted (2026-10-18) · Revisit at Phase 11
**Decision.** Custom image `enterprise-doc-airflow:3.3.2` on `apache/airflow:3.3.2`. Airflow runs Python 3.13; the project needs 3.12 and the locked CPU PyTorch, so a second environment `/opt/app-venv` is built from `uv.lock` (`uv sync --frozen --no-dev --python 3.12`). DAG tasks are `BashOperator`s running `python -m scripts.claim_documents` and `python -m scripts.ingest_document <id>` in it (`env -u PYTHONPATH`). `app/` and `scripts/` are mounted read-only. Secrets are in `airflow/.env` (git-ignored): `HF_TOKEN` yes, `GEMINI_API_KEY` no (ingestion never calls Gemini, I13). The Hugging Face cache is the named volume `hf-cache`. Docling's OpenCV libraries are added with `apt`; the build checks `import cv2, torch, docling`.
**Why.** One lock file and one code path (E-5: identical chunks). No mixing of two dependency sets and two Python versions. A mounted code folder needs no rebuild; the image is rebuilt only when dependencies change.
**Rejected.** `PythonOperator` or TaskFlow importing `app` (dependency conflicts, 3.13 against 3.12). `DockerOperator` (needs the Docker socket). Copying the code into the image (a multi-GB rebuild per change).
**Limits.** RapidOCR models download on first use into the container layer (about 100 s again after a recreate; backlog). The code mount is for development only. **Revisit** at Phase 11 (an app image bakes the code in).

### D-45 · The status lifecycle lives in app code, not in Airflow · Accepted (2026-10-20)
**Changes the Phase 8 plan,** which said Airflow would own `documents.status`.
**Decision.** `documents.status` goes `uploaded`, `processing`, then `processed` or `failed` (plain string, D-19). The logic is in `app/services/document_status.py`: `DocumentStatusService` has `claim_uploaded` (`SELECT ... FOR UPDATE SKIP LOCKED`, oldest first), `reset_orphans` and `mark_*`. `IngestionRunner` marks `processing`, calls `IngestionService`, then marks `processed`, or marks `failed` and re-raises. Both ingestion scripts use the runner. A `failed` document is never claimed again. `reset_orphans` turns leftover `processing` documents back to `uploaded` at the start of each claim. Migration `8c1d5e7a2b96` sets already ingested documents to `processed`. `ChunkService` still does not touch the status (D-22).
**Why.** The status must be true whoever starts the ingestion (D-03). A status set only inside DAG tasks is wrong after a manual run and untestable without Airflow. In app code it is unit-tested with a fake ingestor and integration-tested on the real database in a rolled-back transaction. `SKIP LOCKED` means no document is claimed twice. A final `failed` stops a corrupt PDF from looping.
**Rejected.** Status updates inside DAG tasks. An ENUM (D-19). Automatic retry of failed documents (a poison document would return at every run; to retry by hand, set its status back to `uploaded`).
**Limits.** The failure reason is only in the Airflow task log. A document that kills the worker is reset and tried again at every run (no attempt counter). `reset_orphans` assumes no manual ingestion runs at the same moment (the DAG never overlaps itself). **Revisit.** An `error` column only if a real need appears (D-47); an attempt counter at Phase 14.

### D-46 · One polling DAG: claim, then one mapped ingest task per document · Accepted (2026-10-20) · Revisit at Phase 12
**Decision.** DAG `ingest_documents` runs every minute (`* * * * *`, `catchup=False`, `max_active_runs=1`). `claim` runs `scripts.claim_documents --limit 5` (resets orphans, claims up to 5, prints their ids as JSON on the last line). `build_commands` turns ids into commands (`airflow/dags/ingest_helpers.py`, no Airflow imports, unit-tested in CI). `ingest` is a mapped `BashOperator`, one task per document, `max_active_tis_per_dag=1`, `retries=1` after 1 minute, `execution_timeout` 45 minutes. With nothing to claim the mapped task is skipped and the run ends green in about 2.5 s. The API knows nothing about Airflow. The real import check runs in the container: `airflow dags list-import-errors`.
**Why.** Polling gives "starts by itself" with no coupling: no Airflow credentials in the API, and upload works while Airflow is down (documents wait as `uploaded`). One ingestion at a time because one peaks at about 5.2 GB of the 8 GB VM (E-5). One retry covers a short MinIO or PostgreSQL outage. 45 minutes covers the first run with model downloads (17.5 minutes, E-5).
**Rejected.** The API calling the Airflow REST API. A sensor or event trigger (no event source). Parallel ingestion (memory). More than one retry. One task per stage (each starts a new process, about 66 s start-up on the first attempt, and chunks and vectors would have to be saved between tasks, E-5).
**Cost.** Up to 60 s between upload and the start of ingestion; an idle DAG still runs every minute. **Revisit** if the delay matters in the UI, or ingestion must run in parallel (Phase 12).

---

## UI (Phase 9)

### D-47 · Streamlit UI: HTTP client only, list endpoint, own dependency group · Accepted (2026-10-22)
**Decision.** (1) The UI lives in `ui/`, is a Streamlit app and calls the FastAPI backend over HTTP only; it imports nothing from `app/`. (2) A new endpoint `GET /api/v1/documents` lists documents, newest first, with `limit` and `offset`. (3) No `documents.error` column: the UI shows `failed` and a fixed line that points to the admin log. (4) Streamlit goes in its own uv dependency group, not in the main dependencies. Streamlit version checked 2026-10-21: 1.66.0 (released 2026-10-14), requires Python 3.11 or newer.
**Why.** (1) The API stays the one contract (I2), and the UI can run in another container or machine in Phases 11 and 12. (2) Without a list the UI forgets every document on a page reload; a list endpoint needs pagination (ENGINEERING_STANDARDS section 3). (3) The reason of a failure is needed by the operator, who can read the Airflow log; a column adds a migration and code for no user. (4) The Airflow image installs from `uv.lock` (D-44); Streamlit pulls pandas, pyarrow and more, which that image never uses.
**Rejected.** The UI importing the services directly (couples it to the database and the models, cannot be deployed apart). Streamlit in the main dependencies (a heavier Airflow image and a rebuild for nothing). The error column (no measured need). Settles the Phase 9 revisit of D-45.
**Revisit.** If the UI must show the failure reason (add the column then). Phase 11: the UI as its own container. If `uv sync --no-dev` does not leave the UI group out of the Airflow image, fix that before the tag (checked in step 4).

---

## Evidence

### E-1 · Phase 6 refusal measurements (manual, through the running API, `gemini-3.5-flash-lite`)

| Question (policy corpus) | Top similarity | Result |
|---|---|---|
| Confidential documents no longer needed | 0.4968 | found: shred; page 2, section 2 |
| Paid vacation days (PTO file not ingested) | 0.2833 | refused |
| Paid vacation days (after ingesting it) | 0.5531 | found: 30 days; section 3.1 |
| Standard working hours | 0.5862 | found: 40 h per week; section 2.1 |
| Where may employees smoke (two documents) | 0.6697 | found; cited the Smoke-Free table, four sites correct |
| Alcohol at work | 0.6489 | found; two sources |
| Dress code (file not ingested) | 0.4144 | refused |
| Notice period on resigning (file not ingested) | 0.3946 | refused |

On the Technical Report: a near-miss about a number the paper does not report scored 0.6617 (higher than every answerable question) and the model's `found: false` refused it. A French question retrieved the same chunk as the English one (0.5802 against 0.5792) and was answered in French. Gemini latency 0.6 to 1.1 s, about 1,000 to 1,400 prompt tokens, 40 to 120 output tokens. Ingestion of the three policy PDFs: 21, 11, 32 chunks (pipeline 143, 108, 94 s; embeddings 45, 38, 80 s). A handful of questions, not an evaluation.

### E-2 · Chunk size with the two tokenizers (512-token budget; EmbeddingGemma as the ruler)

| Document | MiniLM (Phase 3) | EmbeddingGemma |
|---|---|---|
| Technical Report | 49 chunks, avg 688 chars, 181 tokens | 31 chunks, avg 1088 chars, 287 tokens |
| ISO 27001 | 72 chunks, avg 691 chars, 136 tokens | 58 chunks, avg 858 chars, 169 tokens |

No chunk exceeds 512 tokens. Embedding speed 1.6 s per chunk on this CPU (58 chunks in 94 s). The ISO PDF: 156 raw chunks, 84 contents junk, 95 with control characters, 14 with the watermark.

### E-3 · Retrieval on the Technical Report (31 chunks, real model, through the API)

| Question | Top result | Similarity |
|---|---|---|
| How does Docling recognize table structure? | Table Structure Recognition, pages 3-4 | 0.5499 (next hits 0.545, 0.531) |
| Which OCR engine for scanned pages? | OCR, page 4 | 0.5792 (References chunk second, 0.43) |
| Vacation days (not answerable) | Performance table, page 5 | 0.0692 |

Identical to the Phase 4 hand check to four digits. Three questions on one document are a smoke test, not evidence for a threshold.

### E-4 · Phase 7 evaluation results (52 questions, version 5, 14 documents, 302 chunks)

| Measure | Baseline, `top_k` 5 | `top_k` 8 |
|---|---|---|
| Expected source in the top 1 / 3 / 5 / 10 | 40/47 (85.1%) / 47/47 / 47/47 / 47/47 | same retrieval |
| MRR | 0.918 | 0.918 |
| Answered when answerable | 46/47 (97.9%), q07 refused | 47/47 |
| Refused when unanswerable | 5/5 | 4/5 (q16 flagged, accepted by hand) |
| Citations cover the expected sources | 46/46 | 47/47 |
| Answers with padding | 4/46 (8.7%) | 3/47 (6.4%) |
| Mean citation precision / citations per answer | 0.969 / 1.67 | 0.979 / 1.72 |

Run files: `data/eval/results/20261017-215229-full-baseline.json` and `20261017-220806-full-topk8.json`. Hand review of the baseline answers (47 answerable): 36 correct, 10 partial (missing a required detail: q02, q03, q04, q05, q09, q13, q26, q41, q42, q47), 1 wrong (q07). Top similarity: answerable 0.382 to 0.735 (mean 0.604); refusals 0.158 to 0.657 (mean 0.419), so no threshold separates them. A full run of 52 questions takes about 335 s (paced); retrieval only takes about 51 s once the model is loaded. Ingesting the 11 remaining PDFs took about 18 minutes. The contact tables are stored as sentences ("Contact = X. Email = Y. Ext. = Z"), which is why a literal "Extension 2500" never matched.

### E-5 · Phase 8 Airflow measurements (2026-10-20, Airflow 3.3.2, Docker VM 8 GB and 4 CPUs, project and Docker disk on an HDD)

| Test | Result |
|---|---|
| Upload through the API to `processed` (`Smoke-Free-Workplace-Policy.pdf`, 11 chunks) | 3 min 51 s (11:34:45 to 11:38:36); `processing` seen after 20 s |
| Same file, Airflow run against the document made on the Windows host | 11 chunks each; text equal 11 of 11; pages and heading equal 11 of 11; largest cosine distance 0.000000 |
| Scheduler memory during that run | 410 MiB before, peak 5.163 GiB, 1.19 GiB after the task |
| Corrupt PDF (`%PDF-1.4` plus text, 33 bytes) | `failed` about 80 s after upload; the retry started 1 minute later and failed in 9 s (`DocumentLoadError`); the status stayed `failed`; every later claim said "claimed 0" |
| Kill test: scheduler container restarted 100 s after `processing` began | stuck `processing` from 18:24:09, `processed` seen at 18:27:26 (polling every 15 s); 11 chunks, not 22 |
| First run of the spike, models not yet downloaded | 17.5 minutes (embedding model about 12 minutes, RapidOCR about 100 s) |
| Same file, models cached | 3 min 6 s (pipeline 79 s, embeddings 25 s) |
| Task start-up before the work begins | about 66 s on the first attempt, 9 s on the retry (disk cache suspected, not proven) |
| Idle DAG run (nothing to claim) | about 2.5 s |

`scripts/check.ps1` at the end of the phase: Ruff clean, 212 tests passed. The DAG import check in the container reported "No data found" (no import errors).
