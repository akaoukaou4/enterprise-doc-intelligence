# ARCHITECTURE

**Question this file answers:** how does the system work **today**?
**Not here:** the plan (ROADMAP), the reasons behind choices (DECISIONS), how to run it (README), scope (PROJECT).

Present tense. Anything not built is listed once, in section 14. Status: end of Phase 14 (2026-11-02). Older versions: Git tags `phase-13`, `phase-12`, `phase-11`, `architecture-before-compress`.

---

## 1. Style and invariants

A **modular monolith**: one Python app in layers, plus PostgreSQL and object storage, an Airflow stack that runs ingestion, and a small Streamlit UI that is a client of the API. Everything runs in Docker from one compose file, locally and on one AWS server (D-02, D-53). A change that breaks an invariant needs a new decision first.

| # | Invariant |
|---|---|
| I1 | `app/pipeline/` imports no FastAPI, Airflow, database or model-serving code. |
| I2 | Routes are thin: HTTP only. Logic lives in services. |
| I3 | Only `StorageService` imports `boto3`. Only `LlmService` imports the Gemini SDK. |
| I4 | One embedding model, one vector size (768), for documents and questions. The column enforces it. |
| I5 | One `EmbeddingService` per API process; the model is built once in it (lock, D-49). |
| I6 | Provenance survives ingestion and retrieval: document id, file name, pages, heading, chunk index. |
| I7 | **Citations are built by code from stored chunks.** The model returns only source numbers. |
| I8 | Model output is untrusted input, validated in code. |
| I9 | Logs hold numbers, ids, timings and the request id. Never question text, answer text, chunk text, a query string or a secret (D-35, D-62). |
| I10 | All configuration goes through one typed `Settings` object. Secrets are never in Git. |
| I11 | Schema changes go through Alembic migrations. |
| I12 | Automated tests never call Gemini. |
| I13 | Only fictional or openly licensed documents are sent to Gemini (free tier may use the data). |
| I14 | After upload, `documents.status` changes only through `DocumentStatusService`. The DAG holds no ingestion logic. |
| I15 | The UI talks to the API over HTTP only and imports nothing from `app/`. |
| I16 | No secret is stored in an image. `HF_TOKEN` is a build secret only (D-53). |
| I17 | On AWS nothing is reachable from the internet: the server group has no inbound rule, the database is not public. Access is an SSM tunnel (D-56). |
| I18 | AWS infrastructure exists only as Terraform code in `infra/`; no resource is created by hand. Secrets reach Terraform only as `TF_VAR_*` environment variables (D-61). |

---

## 2. System overview

```text
USER (browser, Swagger UI, curl, scripts)        (on AWS: through an SSM tunnel)
   v
Streamlit UI (container ui, 8501)  --HTTP only (I15)-->
FastAPI (container api, 8000; EmbeddingGemma inside the image)
  request log middleware: request id on every log line, one line per request (D-62)
  /documents  /search  /ask  /health...
     |             |            |
 DocumentService RetrievalService RagService -> rag_prompt -> LlmService -> Gemini API
     |             |_ EmbeddingService (CPU, in process) _|
 StorageService   PostgreSQL + pgvector: documents (status, attempts, content hash), document_chunks
 boto3            (RDS PostgreSQL on AWS)
 MinIO locally, S3 on AWS

Ingestion, automatic (Airflow containers, same compose):
  DAG ingest_documents, every minute: claim (give up on documents claimed 3 times, reset other leftovers,
  claim uploaded -> processing, count one attempt), then one ingest task per document
  -> scripts/ingest_document.py <id>
  by hand: scripts/ingest_document.py <id>, scripts/ingest_folder.py <folder>
  all go through IngestionRunner (sets processed or failed) -> IngestionService:
    storage -> process_pdf (Docling) -> EmbeddingService -> ChunkService -> document_chunks

By hand: scripts/evaluate.py (host, services directly) -> data/eval/runs/*.json
         scripts/e2e_check.py (HTTP only, any environment, API_URL)
AWS: infra/ (Terraform) creates everything; the server runs the same compose (section 12)
```

With `PRELOAD_EMBEDDING_MODEL=true` (set for the `api` container) a background thread loads the embedding model at start while the API answers requests (D-49).

---

## 3. Repository layout

```text
app/        main.py (create_app, preload) . api/ (deps, health, v1/) . core/ (config, logging, middleware, errors)
            db/ (base, models, session) . services/ (documents, storage, embeddings, chunks, retrieval,
            llm, rag_prompt, rag, ingestion, document_status, info) . evaluation/ (questions, metrics,
            runner, report) . pipeline/ (models, extract, chunk, clean, process) . schemas/
ui/         app.py (the page), api_client.py (HTTP client), Dockerfile
airflow/    Dockerfile, dags/ (ingest_documents.py, ingest_helpers.py), README.md
infra/       Terraform: versions, variables, network, s3, iam, rds, ec2 (+ user_data.sh), outputs, budget,
            .terraform.lock.hcl (committed). State files are git-ignored.
migrations/ Alembic (env.py reads the URL from Settings)
scripts/    ingest_document, ingest_folder, claim_documents, run_pipeline, evaluate, e2e_check,
            smoke_gemini, storage_roundtrip, explore_docling, check.ps1
tests/      unit/ (fakes, run everywhere incl. CI), integration/ (real PostgreSQL and MinIO, self-skipping)
data/       corpus/ (15 fictional PDFs, committed, D-40; one is a prompt-injection test, D-66),
            eval/ (questions.json version 6, results/, runs/ ignored)
docs/       provider_limits.md      .streamlit/config.toml (picker limit 20 MB)
Dockerfile (API image) . docker-compose.yml . docker-compose.aws.yml . .dockerignore . .gitattributes
```

Scripts that import `app` run as modules from the root (`uv run python -m scripts.run_pipeline`). `scripts/e2e_check.py` imports nothing from `app` and needs only `requests`. Test file names are unique across `tests/`. `.gitattributes` keeps `*.sh` on LF line endings (the server runs `infra/user_data.sh`).

---

## 4. API layer

Routes parse HTTP, call a service, format the response (I2). Business endpoints are under `/api/v1`, operational ones at the root (D-20).

| Endpoint | Purpose |
|---|---|
| `GET /health`, `/health/db` | liveness; database reachable |
| `GET /health/model` | 200 `ready`, or 503 `loading` / `idle`; never starts a load; the `api` health check (D-49) |
| `POST /api/v1/documents` | upload a PDF: validate, refuse a duplicate (409), store, insert row (`uploaded`), 201 |
| `GET /api/v1/documents` | `{items, total, limit, offset}`, newest first; `limit` 1 to 100 (20), `offset` 0 or more, else 422 (D-47) |
| `GET /api/v1/documents/{id}` | one document with `status` |
| `DELETE /api/v1/documents/{id}` | row (chunks cascade) and file; 204, 404 unknown, 409 while `processing` (D-50) |
| `POST /api/v1/search` | nearest chunks (inspection) |
| `POST /api/v1/ask` | grounded answer with citations |

Upload does not call Airflow and does not wait: the document stays `uploaded` until the DAG claims it (about a minute); without Airflow it waits. The API has no authentication: locally anyone reaching the ports can upload and delete; on AWS the network closes access (I17).

Services are built per request in `app/api/deps.py`, except the shared `EmbeddingService` (I5). Errors have one shape `{"error": {"code", "message"}}`: `AppError` subclasses (`NotFoundError` 404, `ConflictError` 409, `ValidationFailedError` 422, `ExternalServiceError` 502) are converted by handlers, FastAPI's own errors use the same shape, unexpected exceptions return a generic 500 message and are logged in full. **Services raise `ValidationFailedError` for bad user input** (empty or too long question, `top_k` out of range, bad paging, a bad upload); a plain `ValueError` means an internal bug (chunk and vector counts differ, an empty context, a bad evaluation file) and stays a generic 500 on purpose (D-63). Search, ask and health routes are plain `def` (thread pool, D-21). Request `{question, top_k}`: question stripped, 1 to 1000 characters; `top_k` 1 to 20, default 8 (D-42); else 422 (the request schema usually refuses it first; the service refuses it too).

**Request log** (`app/core/middleware.py`, `app/core/logging.py`, D-62). A middleware gives every HTTP request a new 12-character id (an id sent by the client is ignored, so a client cannot write text into the log), stores it in a context variable, and adds it to the `X-Request-ID` response header. A logging filter puts the id on every log line: `time | LEVEL | request id | logger | message` (`-` outside a request). When the request ends it writes one line, `METHOD path -> status in N ms`, to the logger `app.request`: at INFO, and at DEBUG for paths under `/health` (the UI and Docker poll them). The line holds the path only: never the query string or the body (I9). An unexpected error is built outside the middleware, so its 500 response has no `X-Request-ID` header, but its log line shows 500 with the id. uvicorn's own access line is switched off (`--no-access-log` in the `Dockerfile`), because it repeats the query string.

---

## 5. Data model

**Object storage.** PDFs live under `documents/<document_id>/<filename>`. The database never holds PDF bytes.

**PostgreSQL + pgvector.** Alembic head `a4e2b8c6d1f3` (`b475fddcd445` documents, `3f9a7c2d1e84` vector extension and chunks, `8c1d5e7a2b96` backfills status, `a4e2b8c6d1f3` adds `attempts` and `content_sha256`). The `migrate` container runs `alembic upgrade head` at every start, locally and on RDS.

```text
documents:       id UUID PK . filename . storage_key (unique, never returned) . content_type . size_bytes
                 . status (string: uploaded, processing, processed, failed)
                 . attempts integer NOT NULL default 0 (claims by the DAG, D-64)
                 . content_sha256 varchar(64) NULL, UNIQUE uq_documents_content_sha256 (D-65) . created_at
document_chunks: id UUID PK . document_id FK ON DELETE CASCADE . chunk_index . text
                 . page_numbers integer[] . heading (nullable) . embedding vector(768) NOT NULL . created_at
                 UNIQUE (document_id, chunk_index)
```

Cascade leaves no orphan chunks; the unique constraint stops duplicates on re-processing; `vector(768) NOT NULL` rejects missing or wrong-sized vectors. No vector index: an exact scan is instant at this size (307 chunks, D-07). `content_sha256` is the SHA-256 of the uploaded bytes; it is null for the 14 documents uploaded before Phase 14, and PostgreSQL allows many nulls in a unique column, so those are not checked. The engine is lazy with `pool_pre_ping`; `DATABASE_URL` is optional so tests and CI run without it. `status` is a plain string (D-19); a failure reason lives only in the Airflow task log.

---

## 6. Request flows

**Upload** (`DocumentService.create`, D-19, D-65). Validate (`application/pdf`, `%PDF-` magic bytes, not empty, within `MAX_UPLOAD_MB` 20), compute the SHA-256, look for a document with the same hash (found: `ConflictError` 409 naming that document, nothing stored), `StorageService.upload`, insert the row (`uploaded`). If the insert fails, roll back and delete the file; if the failure is the unique constraint (two identical uploads at the same moment), the answer is the same 409. Only the file content counts: the same text in a different file is not detected.

**Ingestion and status** (`app/services/document_status.py`, D-45, D-64):

```text
uploaded --claim (attempts + 1)--> processing --> processed
                                       +--------> failed   (final: never claimed again)
processing left by a crash --reset_orphans (start of every claim)-->
     attempts < 3: back to uploaded      attempts >= 3: failed (a warning is logged)
```

`claim_uploaded(limit)` takes the oldest `uploaded` rows with `FOR UPDATE SKIP LOCKED`, sets `processing`, adds 1 to `attempts`, commits. `reset_orphans` first marks `failed` every `processing` row with 3 or more attempts (`MAX_ATTEMPTS`), then returns the other `processing` rows to `uploaded`; it returns how many were requeued. `attempts` counts claims by the DAG, not Airflow's own task retry (which happens inside the same run). `IngestionRunner.run` marks `processing`, calls `IngestionService.ingest` (download, `process_pdf`, `embed_documents`, `ChunkService.replace_chunks`), marks `processed`; on any error it rolls back, marks `failed`, re-raises. `scripts/ingest_folder.py` uploads and ingests a folder (dry run unless `--run`; documents with chunks are skipped; one failure does not stop the batch); a document it ingests directly is not claimed, so its `attempts` stays 0.

**DAG `ingest_documents`** (D-46): unpaused at creation, every minute, `max_active_runs=1`, `catchup=False`. `claim` runs `scripts.claim_documents --limit 5` (ids as JSON on the last line); `build_commands` (`ingest_helpers.py`, pure, unit-tested) builds commands; `ingest` is a mapped task, one at a time, one retry after 1 minute, 45-minute timeout, running `python -m scripts.ingest_document <id>` in the app's virtual environment. With nothing to claim the run ends green. A failed document turns its run red; the reason is in the task log. To retry one, set its status back to `uploaded` and its `attempts` to 0. Limit: `reset_orphans` assumes no manual ingestion at that moment. The live kill test of the attempt counter was not run (waived, ROADMAP open question 8); the rule is tested on real PostgreSQL.

**Search.** `RetrievalService.search`: `embed_query`, then `SELECT ... cosine_distance(embedding, q) ... ORDER BY distance, document_id, chunk_index LIMIT top_k`, returning frozen `RetrievedChunk(document_id, filename, page_numbers, heading, text, similarity = 1 - distance)` (D-24). Dense search always returns the nearest chunks, even when nothing answers.

**Delete.** `DocumentService.delete`: `SELECT ... FOR UPDATE`; unknown 404; `processing` 409 (nothing touched); delete row, commit, then delete the file (best effort, logged). The row goes first: an orphan file is harmless, a row pointing to a missing file is not (D-50).

**Ask.**

```text
RetrievalService.search -> no chunks: fixed "no documents" answer, Gemini not called
rag_prompt: system instruction + numbered <source number="n"> blocks (file and section, no pages) + <question>
LlmService.generate_structured -> Gemini -> RagReply {found, answer, source_numbers}
RagService: keep source numbers matching a retrieved chunk (made-up ones dropped);
  found=false -> fixed "not found", no citations; found=true without a valid citation or blank -> "not found";
  else answer + citations built from stored chunks (I7)
response {answer, found, citations[{document_id, filename, page_numbers, heading, text}]}
log: chunk count, similarities, found, cited and dropped numbers, all with the request id (I9)
```

Search and ask read every chunk of every document whatever its status; a deleted document disappears from answers at once. A question during the model load waits for the load. One question leaves these lines in the API log with the same request id: `Retrieved N chunks`, `Gemini call: ...`, `RAG: ...`, and `POST /api/v1/ask -> 200 in N ms`.

---

## 7. Document processing pipeline (`app/pipeline/`)

```text
PDF -> extract (Docling, converter created once)
    -> chunk (HybridChunker, EmbeddingGemma tokenizer, 512 tokens; contents chunks dropped by label
              "document_index"; keeps pages and nearest heading)
    -> clean (remove \x08 and \ufeff and the license watermark line; drop empty chunks)
    -> list[Chunk(text, page_numbers, heading)]
```

`process_pdf(path)` runs the three stages, no storage or database (I1). `chunk_document` accepts a chunker, so tests use fake chunks. Each cleaning rule exists because real PDFs held that junk (D-11). In the Airflow image Docling finds its models in `/opt/hf-cache`, filled at build time (D-54).

**Known limits** (no measurable harm in Phase 7, D-12): text and tables in images unreliable; Docling reports every heading as level 1, so only the nearest heading is kept and some are wrong or missing; a table can lose its header row or split (tables are stored as sentences "Contact = X. Email = Y."); front matter can carry a wrong heading.

**Speed.** About 10 s per page conversion and 1.6 to 2.5 s per chunk embedding on the development CPU. Upload to `processed` for one test document: 202 s locally (E-6), 160 s (E-7) and 170 s (E-8) on AWS, 292 s locally in Phase 14 (not explained, E-9). The one-page `Bicycle-Shed-Policy.pdf` ingested by `ingest_folder` took 72 s for 5 chunks. One ingestion peaks at about 5 GiB in the scheduler container.

---

## 8. Embeddings (`app/services/embeddings.py`)

- Model `google/embeddinggemma-300m`, set by `EMBEDDING_MODEL_ID`, read by the chunker tokenizer and the embedding service (D-06). Another vector size needs a migration.
- `embed_documents(chunks)` embeds `title: <heading or none> | text: <chunk text>` (D-13), returning normalized 768-dimensional vectors in order; `embed_query` uses the model's query prompt.
- **Loading (D-49).** `state` (`ready`, `loading`, `idle`) and a lock: the model is built once even if a preload and a question arrive together. With `PRELOAD_EMBEDDING_MODEL=true` a startup thread (`lifespan` in `app/main.py`) calls `load()`; with it off (default, so tests and CI never need the gated model) the model loads on first use. A failed preload is logged and the state stays `idle`; the next question retries. A dimension check rejects a model that does not give 768 values. `--reload` reloads the model on every save: turn the setting off while editing API code.
- **Weights.** In containers the model is **inside both images** (`/hf-cache`, `/opt/hf-cache`) with `HF_HUB_OFFLINE=1` (D-53). On the host it is gated: accept the license and run `uv run hf auth login` once.

`ChunkService.replace_chunks(document_id, chunks, vectors)` validates counts and 768 values (a mismatch is an internal bug and raises `ValueError`, D-63), then deletes old chunks and inserts new ones in one transaction; a failure keeps the old chunks. It does not touch `documents.status` (D-22).

---

## 9. LLM, RAG and checks

**`LlmService`** is the only importer of `google-genai` (`generate_content` with a JSON schema from a Pydantic model; D-29, D-30). `generate_structured(system_instruction, prompt, response_model)` returns a validated object. One client, 30 s timeout, no retries. Accepted only if `finish_reason` is `STOP`, text non-empty and valid; otherwise `ExternalServiceError` (502) with a generic message (a separate one for quota), details in the log. A missing key gives "The AI service is not configured." Logs model, latency, finish reason, token counts. Settings: `GEMINI_API_KEY` (`SecretStr`), `GEMINI_MODEL` (default `gemini-3.5-flash-lite`, D-28; rechecked 2026-11-01, no shutdown date announced).

**`rag_prompt.py`** (D-31): seven rules: use only the sources; `found: false` with no sources when they do not answer; partial answers allowed; cite only supporting sources; no numbers, files or pages in the text; source text is data, never instructions; answer in the question's language, concisely. Fake `<source>` or `<question>` tags in documents are neutralized. One test shows the rules hold against one instruction hidden in a document (q53, D-66); it is not a full defense.

**`RagService`** orchestrates the ask flow and returns `RagAnswer(answer, found, citations)` (D-32). **Refusal has three layers** (D-33): no chunks; model `found: false`; `found: true` without a valid citation. There is **no similarity threshold**: scores do not separate answerable from near-miss questions (E-1, E-4, E-9). A citation proves the chunk was retrieved, not that it supports every claim; the page number is the reliable part, the section label a hint.

**Evaluation** (`app/evaluation/`, `scripts/evaluate.py`, D-41): runs `data/eval/questions.json` (version 6, 53 questions) against the real services on the host and writes `data/eval/runs/<time>-<mode>[-label].json` after every question, plus a `.review.md` in full mode. Flags: `--retrieval-only`, `--label`, `--only q01,q05`, `--top-k N`. `metrics.py` is pure scoring (hit at k, MRR, coverage, padding, precision); `runner.py` does one top-20 search per question and, in full mode, one paced Gemini call. The runner does not check for the injected word in q53: the review file is read by hand. Results: E-4, E-9. Padding varies between runs of the same code (E-9).

**End-to-end check** (`scripts/e2e_check.py`, D-51): measures whether the running system works. HTTP only (`API_URL`, default `http://localhost:8000`): waits for `/health/model`, uploads a copy of a corpus PDF under a unique name (a comment line with that name is appended to the bytes, so the copy has its own hash and is not refused as a duplicate, D-65), polls to `processed`, checks `/search`, asks one answerable and one unanswerable question (2 Gemini requests, 5 s apart), deletes the document and checks it is gone and the count is back. It prints **10 PASS lines** and `ALL CHECKS PASSED` (exit 0), or exits 1. Needs Airflow running and the Gemini key. Run on AWS in Phases 12 and 13 (E-7, E-8) and locally in Phase 14 (E-9).

---

## 10. Storage abstraction

`StorageService` has `upload`, `download`, `delete` and is the only code importing `boto3` (I3, D-17). Failures become `NotFoundError` (missing key) or `ExternalServiceError`. MinIO versus S3 is configuration: with `MINIO_ENDPOINT` set boto3 uses MinIO with the given keys; with it empty (AWS) boto3 talks to S3 with the instance role's credentials, region from `AWS_DEFAULT_REGION`. No code differs.

---

## 11. Configuration and secrets

One typed `Settings` (`app/core/config.py`) reads environment variables and `.env`; settings are added only when a phase needs them.

| Group | Settings |
|---|---|
| Application | `APP_NAME`, `APP_ENV`, `DEBUG`, `LOG_LEVEL` |
| Database | `DATABASE_URL` (optional so CI runs without it) |
| Object storage | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` |
| Uploads | `MAX_UPLOAD_MB` |
| Embeddings | `EMBEDDING_MODEL_ID`, `PRELOAD_EMBEDDING_MODEL` (default false) |
| LLM | `GEMINI_API_KEY` (secret), `GEMINI_MODEL` |

Search limits (`DEFAULT_TOP_K` 8, `MAX_TOP_K` 20, `MAX_QUESTION_CHARS` 1000), list limits (`DEFAULT_LIST_LIMIT` 20, `MAX_LIST_LIMIT` 100) and `MAX_ATTEMPTS` (3, in `document_status.py`) are constants in the services.

**The single `.env`** (git-ignored; `.env.example` is the template) serves three readers:
- **Docker Compose** substitution. Locally required: `HF_TOKEN` (build secret only, not a `Settings` field) and `GEMINI_API_KEY`; defaults for `POSTGRES_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`. On AWS the server's `.env` holds four values: `RDS_HOST`, `RDS_PASSWORD`, `HF_TOKEN`, `GEMINI_API_KEY` (mode 600, written from hidden prompts, never in Git; `RDS_*` are compose variables).
- **The containers** do not read the file (`.dockerignore` excludes it); compose gives them `DATABASE_URL`, storage settings and `HF_HUB_OFFLINE=1`; `api` also gets `GEMINI_API_KEY` and `PRELOAD_EMBEDDING_MODEL=true`. Airflow containers get no Gemini key (I13) and no Hugging Face token.
- **The host app** reads the `localhost` values in the same file.

**Terraform** reads two variables from the terminal only: `TF_VAR_rds_password` (letters and digits, 12 or more) and `TF_VAR_budget_email`. Neither is in a file (I18).

**UI.** `API_URL` (default `http://localhost:8000`; `http://api:8000` in its container), read by `ui/api_client.py` (I15). The picker limit is Streamlit's `server.maxUploadSize` = 20 MB in `.streamlit/config.toml`, repeating `MAX_UPLOAD_MB` on purpose (D-52).

---

## 12. Containers, AWS and Terraform

### 12.1 Containers (`docker-compose.yml`, D-53, D-54)

One command starts the whole system: `docker compose up -d --build`. Containers reach each other by service name.

| Service | Image | Role |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg18` | application database (host port 5433 for tools) |
| `minio`, `minio-init` | MinIO, `mc` | object storage; the init creates the bucket once |
| `migrate` | `enterprise-doc-api` | `alembic upgrade head` once, then exits |
| `api` | `enterprise-doc-api` | FastAPI 8000, memory limit 3 GB, health check `/health/model` |
| `ui` | `enterprise-doc-ui` | Streamlit 8501, health check `/_stcore/health` |
| `airflow-db`, `airflow-init` | `postgres:16`, Airflow image | metadata database (D-43); init migrates it and creates the login |
| `airflow-apiserver`, `-scheduler`, `-dag-processor` | `enterprise-doc-airflow` | UI 8080 (login `airflow` / `airflow`), the DAG and the ingestion tasks |

**Start order:** `postgres` healthy, `migrate` done, `api` (also needs `minio-init`), `ui`; `airflow-db` healthy, `airflow-init` done, the three Airflow services (the scheduler also waits for `migrate` and `minio-init`). Restart policy `on-failure` for apps, `unless-stopped` for `postgres` and `minio`.

**Images** (sizes: E-6, E-7):
- **API** (`Dockerfile`): two stages on `python:3.12-slim`; the builder runs `uv sync --frozen --no-dev` (CPU PyTorch) and downloads EmbeddingGemma with `HF_TOKEN` as a BuildKit secret; the runtime stage adds the system libraries, the environment, code and model, runs as non-root, sets `HF_HUB_OFFLINE=1`. It starts `uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log` (D-62). **The import check that fails the build runs in this stage**, including `psycopg`.
- **Airflow** (`airflow/Dockerfile`): Airflow 3.3.2 plus the app in its own virtual environment `/opt/app-venv` (Python 3.12 from `uv.lock`). Docling and EmbeddingGemma models are baked into `/opt/hf-cache`; the RapidOCR models are not proven offline (D-54). Code and DAG are copied in.
- **UI** (`ui/Dockerfile`): only the `ui` dependency group, the UI code and `.streamlit/config.toml`.
- Never push these images to a public registry: the embedding model is gated.

**Volumes:** `postgres_data`, `minio_data` (your documents), `airflow-db-volume`, `airflow-logs`. `docker compose down` keeps them; `down -v` deletes them.
**Memory** (E-6, E-7): all containers idle about 2.4 GiB; one ingestion adds about 4.3 GiB in the scheduler. One ingestion at a time. The margin is as thin on the 8 GB Docker VM as on the 8 GiB AWS instance.
**Rebuild time:** a full rebuild with a lost build cache took 4,364 s (about 73 minutes) on the laptop's hard disk in Phase 14; the cause is not proven (E-9).

### 12.2 AWS and Terraform (Phases 12 and 13, D-55 to D-61)

The same compose and images run on one EC2 server; the infrastructure is Terraform code in `infra/` (provider `hashicorp/aws ~> 6.0`, locked at 6.71.0; Terraform `~> 1.16`, used 1.16.6). Region `eu-north-1`, default VPC (read as a data source, no network is created). **Nothing exists on AWS between sessions:** `terraform apply` builds it, `terraform destroy` removes it. Phase 14 did not change `infra/`.

```text
laptop --(aws login, SSM tunnel)--> EC2 enterprise-doc-server (no inbound rule)
                                      docker compose -f docker-compose.yml -f docker-compose.aws.yml
                                      |-- RDS enterprise-doc-db (PostgreSQL 18.3 + pgvector, private)
                                      |-- S3 enterprise-doc-intel-483920 (through the instance role)
                                      '-- Gemini API (outbound only)
```

| File | Creates |
|---|---|
| `network.tf` | server group (0 inbound, explicit allow-all egress), database group (5432 from the server group only) |
| `s3.tf` | private bucket, all public access blocked, `force_destroy = true` |
| `iam.tf` | role and instance profile `enterprise-doc-ec2-role` (`AmazonSSMManagedInstanceCore` plus policy `enterprise-doc-s3-access`: Get, Put, DeleteObject on objects, ListBucket on the bucket) |
| `rds.tf` | PostgreSQL 18.3, `db.t4g.micro`, 20 GiB gp3 encrypted, single-AZ, not public, user `appadmin`, database `enterprise_docs`, `skip_final_snapshot = true` |
| `ec2.tf`, `user_data.sh` | `m7i-flex.large` (8 GiB), Amazon Linux 2023, 50 GiB gp3, no key pair, public IP (outbound only), IMDSv2 required with hop limit 2, newest-AMI changes ignored, subnet `sort(data.aws_subnets.default.ids)[0]`; the script adds a 4 GB swap file, Docker, git, and the Compose v5.6.1 and Buildx v0.38.1 plugins |
| `budget.tf` | `monthly-cap`, $20 a month, alerts at 85% and 100% actual and 100% forecast, by email |
| `outputs.tf` | `instance_id`, `rds_host`, `bucket` |

`force_destroy` and `skip_final_snapshot` are safe only for the fictional corpus (D-61); remove both before any real data. The server's subnet is the first id of the **sorted** default-VPC subnet list, so the choice is stable; a different id would replace the instance, and whether the sorted pick equals the one used in Phase 13 was not checked with a plan (ROADMAP open question 6). The state file is local, git-ignored, and contains the database password.

**`docker-compose.aws.yml`** (D-58) overrides the base file: `postgres`, `minio` and `minio-init` get profile `local`; `migrate`, `api` and `airflow-scheduler` get the RDS `DATABASE_URL` (`sslmode=require`), the bucket, `AWS_DEFAULT_REGION=eu-north-1` and empty `MINIO_*` keys (so boto3 uses the role); `depends_on` entries for removed services are cut with `!reset` and `!override`, so `check-yaml` runs with `--unsafe`. `airflow-db` still starts.

**Access (I17, D-56).** No SSH, no public URL. With the AWS CLI and the Session Manager plugin: `aws login`, then

```text
aws ssm start-session --region eu-north-1 --target <instance_id> --document-name AWS-StartPortForwardingSession --parameters "portNumber=8501,localPortNumber=18501"
```

opens the UI at http://localhost:18501. A shell on the server: `aws ssm start-session --region eu-north-1 --target <instance_id>`, then `bash`; Docker commands need `sudo` (`ssm-user` is not in the `docker` group). Logs are read there with `sudo docker compose -f docker-compose.yml -f docker-compose.aws.yml logs api`; there is no CloudWatch (D-67). Run `aws logout` when done. The instance role cannot read budgets or other account data (least privilege).

### 12.3 Rebuild from nothing (about 25 minutes plus ingestion)

1. On the laptop, in `infra/`: `terraform init`, set `TF_VAR_rds_password` and `TF_VAR_budget_email` in the terminal, `terraform plan` (check that it only creates), `terraform apply` (RDS takes about 7.5 minutes). Note `instance_id` and `rds_host`.
2. Open a shell on the server (above), `bash`, clone the repository with a short-lived fine-grained GitHub token (Contents read-only, one repository) typed at a hidden prompt, then reset the remote URL to the plain one (D-57).
3. Write `~/enterprise-doc-intelligence/.env` (`RDS_HOST`, `RDS_PASSWORD` equal to the Terraform one, `HF_TOKEN`, `GEMINI_API_KEY`) from hidden prompts, with `umask 077`; check the lengths before writing and the file mode after.
4. `sudo env COMPOSE_PARALLEL_LIMIT=1 docker compose -f docker-compose.yml -f docker-compose.aws.yml build` (243.7 s in Phase 13), then the same with `up -d`; `migrate` applies the four revisions.
5. Check: `docker run --rm --network host -v "$PWD":/w -w /w -e API_URL=http://localhost:8000 python:3.12-slim sh -c "pip install -q requests && python scripts/e2e_check.py"` with `sudo`. To load the corpus, upload `data/corpus/*.pdf` with `curl -F "file=@<pdf>;type=application/pdf"`; ingestion took about 40 minutes for 14 documents (E-7), so allow a little more for 15.
6. Remove the GitHub token. When finished: `terraform destroy` (about 2 minutes), then read-only checks that no instance, database, volume, security group, bucket, role or budget is left.

Cost and plan: the Free plan allows only small EC2 types (D-59), ends on 2027-04-29 and closes the account unless upgraded. Credits were $140.00 on 2026-10-30 and $159.00 on 2026-11-02; Phases 12 and 13 cost about $1 (E-9).

---

## 13. Local environment, tests and UI

**Local (Windows).** The project is on D:, with the uv and Hugging Face caches also on D: (D-10). Docker Desktop on WSL 2, memory limit 8 GB, disk image on D:. The host Python environment (`uv sync`, CPU-only PyTorch) serves development, tests, `evaluate.py` and `e2e_check.py`. Gates: `scripts/check.ps1` (Ruff lint and format, pytest, and, when Terraform is installed, `terraform fmt -check`, `init -backend=false` and `validate`; without Terraform it prints a warning and skips them), pre-commit (including a secret scanner, `end-of-file-fixer` and `check-yaml --unsafe`), a pre-push hook, GitHub Actions CI on every push. CI runs Ruff lint and format, pytest and the three Terraform checks (`hashicorp/setup-terraform@v3`, Terraform `~1.16.0`); it does not build the images (the gated model needs a token).

**Tests** (D-26, D-37). Unit tests replace dependencies with fakes (session, storage client, embedding model, LLM client, services, the UI client's HTTP session): fast, no database, MinIO or model, run in CI. Integration tests use real PostgreSQL and MinIO, skip themselves when unavailable, and remove only what they created; retrieval tests use hand-made unit vectors, list tests use documents dated 2099 with status `processed` so the DAG never claims them, and the status tests run inside a transaction that is rolled back, with every existing document set to `processed` inside it. Checked by hand: real Docling, the real embedding model, real Gemini, the real DAG, the Streamlit screens, and the whole running system by `scripts/e2e_check.py`. Test status: ROADMAP handoff.

**UI** (`ui/`, D-47, D-48). A client of the API (I15).
- `ui/api_client.py` is the only HTTP code: `upload_document`, `list_documents`, `ask`, `model_status`; timeouts 15 s list, 60 s upload, 90 s ask, 5 s status; every failure becomes an `ApiError` with a safe message; `model_status` never raises. No delete method: the UI offers no delete.
- `ui/app.py` draws: a model status line (checked every 3 s until ready, then every 30 s); an upload picker (20 MB); a table of the newest 50 documents (file, status, time), refreshed every 3 s only while a document is `uploaded` or `processing`, with a warning on `failed`; an ask form with a `top_k` expander, the answer and one expander per source (file, pages, section, chunk text); `found: false` shows a warning and no sources.
- Limits: a question during the model load waits (up to about a minute on a cold disk); only the client has automated tests; the picker and API upload limits must change together; an upload of a duplicate file shows the API's 409 message.

---

## 14. Not built yet

CloudWatch logs and alarms (a future improvement, D-67). A restricted IAM user for the CLI (it uses the account's full-access role), a secret store for the server's `.env`, and authentication in the app (the network closes access, I17). Remote Terraform state. A `terraform plan` check that the sorted subnet pick does not replace the server. An image build in CI. An e2e run from the laptop through the tunnel. A content hash for the 14 documents uploaded before Phase 14, and detection of the same text in a different file. A live kill test of the attempt counter. Small known gaps (no failure-reason column, no automated tests of the UI screens, no delete button in the UI, the embedding model stored in two images): ROADMAP backlog. Hybrid retrieval, reranking, a vector index and a similarity threshold are absent because the Phase 7 evaluation showed no need (D-07, D-33, E-4), and the Phase 14 evaluation with a 15th document did not change that (E-9).
