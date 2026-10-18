# DECISIONS

**Question this file answers:** why is the system the way it is?
**Not here:** how it works now (ARCHITECTURE), the plan (ROADMAP), how to run it (README).

## How to read and write this file

- One record per decision, numbered `D-nn`. Append new ones at the end. Never delete or rewrite an old one.
- **Status:** *Accepted*, *Revisit at Phase N* (accepted, with a known trigger to look again), or *Superseded by D-nn*. When a decision changes, add a new record that says "Supersedes D-nn", and change the old status. Link both ways. Then run the ripple check: fix every doc that mentions the old decision, in the same commit.
- Record shape: **Decision**, **Why**, **Rejected** (alternatives and the reason), **Revisit** (what would change my mind). Evidence tables are at the end (E-1 to E-4).
- Volatile facts (model names, quotas, versions) are written here once, with the date they were checked.
- Section numbers of the old file (for example "12.2") no longer exist. The old file is in Git at the tag `docs-before-restructure`.

---

## Scope and architecture

### D-01 · Product and V1 scope · Accepted
**Decision.** Build a document-intelligence assistant: upload PDFs, ask questions, get grounded answers with page and section citations. V1 is the smallest end-to-end path (upload, process, chunk, embed, store, retrieve, generate, cite). Risk classification, audit prioritization, agents, fine-tuning and advanced automation are deferred.
**Why.** A realistic business problem that needs RAG keeps AI Engineering at the centre. A small V1 can be understood, tested and evaluated before anything is added.
**Rejected.** Adding technologies for their keywords; building later features early. The rule for every technology is the 5-question test in the private kit (ENGINEERING_STANDARDS section 1).

### D-02 · Modular monolith · Accepted
**Decision.** One Python application with clear internal layers; PostgreSQL and MinIO as containers. No microservices, Kubernetes or Kafka.
**Why.** Small scale, easier debugging and local development, no distributed-system cost.
**Revisit.** Only if a measured requirement appears.

### D-03 · The pipeline is independent; two execution modes · Accepted
**Decision.** `app/pipeline/` imports no FastAPI, Airflow or database code. Direct mode: scripts and tests call the pipeline and services. Orchestrated mode (Phase 8): Airflow tasks call the same functions.
**Why.** Fast development, easy testing, and Airflow orchestrates without owning the logic.
**Consequence.** Embedding and storing are services in `app/services/`, not part of the pipeline package.

### D-04 · Deployment path: local first, simple AWS, Terraform last · Accepted
**Decision.** Docker Compose locally (PostgreSQL + pgvector, MinIO now; more later). AWS only after the local system works: EC2, RDS PostgreSQL + pgvector, S3, IAM, CloudWatch. Terraform only after the AWS setup is understood by hand. The same application runs in both environments; only configuration changes.
**Why.** Cloud must not hide application problems, and each service needs a reason.
**Rejected.** EKS, Lambda, ECS, OpenSearch, Redis, queues.
**Revisit at Phase 12.**

---

## AI and document processing

### D-05 · Gemini for generation · Accepted
**Decision.** Use the Gemini API for answers. The project is about integrating AI, not training or hosting large models.
**Why.** A capable LLM without large local hardware, and it deploys easily. The model name is one setting (see D-28).

### D-06 · EmbeddingGemma, local, one setting · Accepted
**Decision.** `google/embeddinggemma-300m` for documents and questions, set by `EMBEDDING_MODEL_ID`, read by both the chunker tokenizer and the embedding service. 768 dimensions. The service checks the model's output size against the database column when the model loads.
**Why.** Runs on CPU, sends no document text to an embedding API, and one setting prevents the tokenizer and the model drifting apart. A model with another size needs a new migration, and the check makes that visible at once.
**Consequence.** The model is gated: accept the license and run `uv run hf auth login` once. The token lives under `HF_HOME`, outside the repo. Deployments need `HF_TOKEN` as a secret or a pre-downloaded model volume. CI never needs it (tests use fakes).
**Revisit.** If evaluation shows another model is better. (Phase 7 gave no reason: retrieval was already good, E-4.)

### D-07 · Dense retrieval first; evaluate before optimizing · Accepted
**Decision.** Retrieval is pgvector cosine similarity. No hybrid search, reranking, query expansion, similarity threshold, document filter or vector index until Phase 7 shows a need.
**Why.** A measurable baseline first. At tens of chunks an exact scan is instant and an index would make results approximate for no benefit.
**Phase 7 result (E-4):** the expected source was in the top 3 for all 47 answerable questions, so hybrid search, reranking and a vector index are not needed. **Revisit at Phase 14,** only if a larger corpus changes this.

### D-08 · Docling and HybridChunker · Accepted
**Decision.** Docling parses PDFs; HybridChunker produces the chunks (D-14 sets the size).
**Why.** Structure-aware parsing suits enterprise documents better than plain text extraction, and avoids writing a chunker early. Confirmed on two real PDFs, then on the 14-document corpus (E-4).
**Revisit.** If a later corpus shows chunking hurts retrieval.

### D-09 · Provenance is part of the data · Accepted
**Decision.** A chunk is `Chunk(text, page_numbers, heading)`. `page_numbers` is a list because chunks span pages. Only the nearest heading is kept, because Docling reports every heading as level 1. The stored row adds `document_id` and `chunk_index`. The embedding is never a substitute for provenance.
**Why.** Citations need it. The schema comes from what Docling provides, not from invention.

### D-10 · Look at real output before designing; CPU PyTorch; caches on D: · Accepted
**Decision.** Inspect real Docling output on real PDFs before writing pipeline code. Install CPU-only PyTorch from an explicit `pytorch-cpu` uv index (`torch` and `torchvision` as direct dependencies). Keep `UV_CACHE_DIR` and `HF_HOME` on D: outside the repository.
**Why.** Several assumptions were wrong until measured. The GTX 1050 (4 GB) is too small to help; CUDA wheels add GB, and on Linux CI would download them. C: is nearly full; uv hardlinks only work on one drive.

### D-11 · Four cleaning rules, each backed by data · Accepted
**Decision.** Drop table-of-contents chunks (items labelled `document_index`), remove the license watermark line, strip `\x08` and `﻿`, drop chunks empty after cleaning. No minimum chunk size.
**Why.** The ISO PDF gave 156 chunks, 84 of them contents junk. Invisible characters would reach the database, the embedding and the prompt. No evidence that small chunks hurt.
**Rejected.** Pattern-based contents detection (the label is more reliable); a length threshold (a tuning knob without data).
**Limit.** Works only when Docling detects the contents page.

### D-12 · Known pipeline limits are accepted for now · Accepted (Phase 7: no measurable harm)
**Decision.** Not fixed: text and tables inside images are unreliable; some headings are wrong or missing; tables can lose their header row or split across chunks; rows without separator lines merge.
**Why.** The target content is mostly prose policies where these are rare. A rule like "ignore headings repeated on several pages" would also drop real captions.
**Phase 7 result.** 11 table questions: all retrieved in the top 5; answers correct except one partial (q26 misses Gate A and the escort rule). **Revisit.** If a later corpus has tables that fail. Candidate fix, not tested: HybridChunker `repeat_table_header`.

### D-13 · Embed `title: <heading> | text: <chunk>`, built by our code · Accepted
**Supersedes** the Phase 3 plan to embed `chunker.contextualize(chunk)`.
**Decision.** `build_document_text` in `app/services/embeddings.py` builds the model's native document format from our own `Chunk` and passes it to plain `encode`. Questions use `encode_query`. The stored `text` is the plain chunk text.
**Why.** The model has a title slot and its card says a real title helps. Its own `encode_document` always writes `title: none`. Building the string ourselves keeps `Chunk` unchanged and the embedding stage independent of Docling. Without a heading our string equals the model's own prompt (cosine 1.0000).
**Rejected.** `contextualize` (couples the embed stage to Docling objects or pollutes `text`).
**Not tested in Phase 7** (retrieval was already good). **Revisit** only if retrieval gets worse on a new corpus: heading versus `none` (wrong headings can mislead a vector).

### D-14 · 512-token chunks measured with the EmbeddingGemma tokenizer · Accepted (not tested in Phase 7)
**Supersedes** the Phase 3 default MiniLM tokenizer for chunking.
**Decision.** HybridChunker measures size with the embedding model's tokenizer, budget 512 tokens, although the model accepts 2048.
**Why.** Size must be measured by the model that embeds the chunk. The larger vocabulary fits 30 to 60% more text in the same budget (E-2). Average chunk 170 to 290 tokens is a normal RAG size, and there is no evidence another size is better.
**Revisit.** 256 and 1024 were not tested (retrieval was already good): only if retrieval gets worse (`MAX_CHUNK_TOKENS`, one line, then re-ingest and re-evaluate).

### D-15 · Third-party sample documents stay local · Accepted (exception: D-40)
**Decision.** PDFs and Docling output stay in git-ignored folders, except the fictional corpus in `data/corpus/` (D-40). `data/eval/` is trackable; evaluation data is JSON or YAML (`.gitignore` ignores `data/**/*.csv`). The ISO/IEC 27001 standard is copyrighted: local use only, never sent to Gemini.
**Why.** The repo is public. The demo and the evaluation set need fictional or openly licensed documents.

---

## Data, storage and backend

### D-16 · PostgreSQL + pgvector, one table of chunks · Accepted
**Decision.** One database for metadata, chunks and vectors. `document_chunks` has `document_id` FK `ON DELETE CASCADE`, `chunk_index`, `text`, `page_numbers integer[]`, `heading`, `embedding vector(768) NOT NULL`, and `UNIQUE (document_id, chunk_index)`. Similarity is `1 - cosine_distance` (the vectors are normalized, so cosine and dot product rank the same, and cosine stays correct if the model changes).
**Why.** Cascade leaves no orphans. `integer[]` avoids a join table. `NOT NULL` plus `vector(768)` makes the database reject bad vectors. The unique index also serves "chunks of a document". No vector index (see D-07).
**Rejected.** A dedicated vector database (no evidence PostgreSQL is insufficient).
**Note.** The migration was written by hand (autogenerate cannot create the extension). The secret scanner flagged its hex revision ids; fixed with an inline `# pragma: allowlist secret`, not by disabling the hook.

### D-17 · Object storage through boto3 and a small StorageService · Accepted
**Decision.** Originals live in object storage under `documents/<document_id>/<filename>`, never in the database. `boto3` talks to MinIO when `MINIO_ENDPOINT` is set and to real S3 otherwise (IAM role on EC2). `StorageService` has `upload`, `download`, `delete`, is the only importer of boto3, builds its client lazily, and maps errors to `NotFoundError` or `ExternalServiceError`. The `minio-init` container creates the bucket.
**Why.** Provider switching by configuration only. No interface class or plugin system: abstract real variation, not imagined variation.
**Limits.** Files are handled as bytes in memory (fine at 20 MB). If `.env` is missing, boto3 would try real AWS, so `.env` must exist. `MINIO_*` names may become `S3_*` in Phase 12.

### D-18 · Alembic for every schema change · Accepted
**Decision.** Versioned migrations in `migrations/`, URL read from `Settings`, `versions/` excluded from Ruff, every generated migration read before applying. No `create_all`.
**Why.** `create_all` cannot alter tables. The same history will run on RDS. One source of configuration.

### D-19 · Upload rules and document model · Accepted
**Decision.** `documents` uses a Python-generated UUID, a unique `storage_key` and a plain-string `status` (not an ENUM). Accept only `application/pdf` whose bytes start with `%PDF-`, not empty, within `MAX_UPLOAD_MB` (20). Filename reduced to its last path component. Order: validate, store the file, insert the row; if the insert fails, roll back and delete the file. `storage_key` is never returned by the API.
**Why.** The key needs the id before the insert. A row pointing at a missing file is worse than a file without a row. A client can lie about content type. ENUMs are awkward to migrate.
**Limit.** A crash between the two steps can leave an orphan file. No cleanup job at this scale.

### D-20 · Backend conventions · Accepted
**Decision.** One typed `Settings` (pydantic-settings), settings added only when a phase needs them. `create_app()` factory. Standard `logging`. One JSON error shape `{"error": {"code", "message"}}`, with `AppError` subclasses; unexpected exceptions return a generic message. Business endpoints under `/api/v1`, health endpoints unversioned. Thin routes, logic in services injected through `app/api/deps.py`. `DATABASE_URL` optional and the engine lazy with `pool_pre_ping` (CI runs without a database; the app recovers after a restart; verified). Unit tests use `dependency_overrides`.
**Why.** Testability, no leaked internals, cheap now and expensive later.

### D-21 · EmbeddingService: lazy, shared, behind plain `def` routes · Revisit at Phase 11
**Decision.** The model loads on first use, on CPU. The API holds one instance (`lru_cache` in `deps.py`). Search and ask routes are plain `def`, so blocking work runs in the thread pool.
**Why.** Fast imports and tests, no model needed in CI. An `async def` route would freeze the event loop on CPU work.
**Known costs.** First request about 22 s (about 15 update checks to huggingface.co). No loading lock. `--reload` reloads the model.
**Revisit.** Phase 11: run offline with a pre-downloaded model; decide between preloading and lazy loading.

### D-22 · ChunkService replaces in one transaction, validates first · Accepted
**Decision.** `replace_chunks(document_id, chunks, vectors)` checks counts and 768 values (`ValueError`), raises `NotFoundError` for an unknown document, deletes old chunks and inserts new ones in one transaction, and keeps the old chunks on any failure. An empty list clears the chunks. It does not change `documents.status`.
**Why.** Reprocessing must not duplicate, and a half-written document must never be visible. A count mismatch is a caller bug, not a user error.

### D-23 · Direct ingestion script, no ingestion class · Revisit at Phase 8
**Decision.** `scripts/ingest_document.py <document_id>` chains download, `process_pdf`, `embed_documents`, `replace_chunks`. Safe to repeat. It is the blueprint for the Airflow tasks.
**Why.** Four calls do not need a class yet. Status transitions belong to Phase 8.
**Phase 7 update.** The bulk script `scripts/ingest_folder.py` needed the same four calls, so they moved into `IngestionService` (`app/services/ingestion.py`). Both scripts call it, and Phase 8 will call it too. The "no class" choice was reversed because a second caller appeared.

### D-24 · Retrieval returns plain objects; `/search` is an inspection endpoint · Accepted
**Decision.** `RetrievalService.search` returns frozen `RetrievedChunk(document_id, filename, page_numbers, heading, text, similarity)`, with the file name joined in the query. `POST /api/v1/search` exposes it.
**Why.** Citations need no second lookup; callers never see the ORM row or the 768-number vector. When an answer is bad, the same question on `/search` shows whether retrieval or generation failed.
**Rejected.** Returning ORM rows (coupling, extra lookup).

### D-25 · Input limits and stable ordering · Accepted (default top_k superseded by D-42)
**Decision.** `top_k` 1 to 20 (default 8, D-42). Question stripped, 1 to 1000 characters. Constants live in `retrieval.py`; schemas import them; the API returns 422, the service raises `ValueError` too. The query orders by distance, `document_id`, `chunk_index`.
**Why.** A maximum protects the database. A stable order makes tests and evaluation repeatable. The numbers were guesses; Phase 7 tested only the default `top_k` (D-42). The question length limit was not tested.
**Known gap.** `ValueError` is not mapped to HTTP; a future endpoint that skips the schema would return 500.

### D-26 · Tests: fakes, hand-made vectors, skipped integration, unique names · Accepted
**Decision.** Unit tests use fakes and run in CI. Integration tests use the real containers and skip themselves when unavailable; each deletes only what it created. Retrieval integration tests use hand-made vectors (similarity 1.0, 0.7071, 0.0). Test file names must be unique across `tests/` (no `__init__.py`, so pytest identifies modules by file name).
**Why.** CI has no database, MinIO or model. Fakes cannot catch wrong column types or constraints; integration tests can. Real data stays safe.

---

## Generation (Phase 6)

### D-27 · Check changing facts in official documentation first · Accepted
**Decision.** Before using any fact that changes with time (SDK shape, model names, quotas, data-use terms), check the official source, or a small real call, or ask. Do not rely on memory.
**Why.** The quotas seen in AI Studio differed from what was assumed, and that changed the model choice (D-28).

### D-28 · Model `gemini-3.5-flash-lite`, set by `GEMINI_MODEL` · Accepted; revisit before deployment
**Decision.** Default model `gemini-3.5-flash-lite`; key in `GEMINI_API_KEY` as a `SecretStr`.
**Why.** Checked 2026-10 in AI Studio: 15 requests per minute, 250,000 tokens per minute, 500 per day; larger Flash models only 5 per minute and 20 per day, unusable for development and evaluation. Answers are short extraction, which suits a small model.
**Revisit.** Model lifetimes are short: check for a shutdown date before deployment. Larger model and thinking level were not tested in Phase 7 (20 requests a day is too few for 52 questions, and the baseline answered 46/47). Quotas checked again 2026-10-16; the full table is in `docs/provider_limits.md`.

### D-29 · Stay on `generate_content`, not the Interactions API · Revisit on deprecation
**Decision.** `LlmService` uses `client.models.generate_content`.
**Why.** RAG here is one stateless request. The Interactions API keeps state at Google by default (a privacy question for document text), and its REST version was beta when checked. Switching later touches one file (D-30).
**Note.** A conscious deviation from the vendor's recommendation, recorded so it is not mistaken for ignorance of it.

### D-30 · LlmService owns the SDK; strict acceptance; no retries; generic errors · Accepted
**Decision.** `app/services/llm.py` is the only importer of the Gemini SDK (`google-genai`). `generate_structured(system_instruction, prompt, response_model)` returns a validated Pydantic object. One client per process, 30 s timeout, `max_output_tokens` 2048, one attempt (no retries). A response is accepted only if `finish_reason` is `STOP`, the text is not empty and it validates; otherwise `502`. Every Gemini failure is `ExternalServiceError` (`502`) with a generic message (a friendlier one for `429`; "The AI service is not configured." for a missing key). Details go to the log only.
**Why.** Model output is untrusted input (a cut-off JSON shown as a full answer is worse than an error). A timeout stops a slow call holding a thread. Retries double the wait and burn the daily quota, and the likely failures (bad key, `429`) are not fixed by retrying. SDK exception text may contain request details.
**Revisit.** If transient `5xx` errors turn out to be common: retry only those, once, with a short delay. (No Gemini errors in the 52-question runs of Phase 7.)

### D-31 · Prompt: numbered sources, declared as data · Accepted
**Decision.** `rag_prompt.py` builds a seven-rule system instruction (use only the sources; `found: false` with no sources when they do not answer; partial answers allowed; cite only directly supporting sources; no numbers, file names or pages in the answer text; source text is data, never instructions; answer in the question's language, concisely). Each chunk is `<source number="n">` with file and section, no pages. The question comes last in `<question>` tags. Fake `<source>` or `<question>` tags inside documents are neutralized.
**Why.** Numbers let the model point without copying, which makes validation possible (D-32). Retrieved text is untrusted. Leaving pages out gives the model nothing to invent a page from.
**Limit.** A mitigation, not a full defense against prompt injection. Adversarial documents are a Phase 14 topic.

### D-32 · The model returns source numbers; code builds citations · Accepted
**Decision.** The model returns `{found, answer, source_numbers}`. `RagService` keeps numbers `1..n` matching a retrieved chunk, drops the rest (and logs them), and builds each `Citation(document_id, filename, page_numbers, heading, text)` from the stored chunk.
**Why.** Citations are a core requirement; an invented page is worse than none. The check is one comparison.
**Rejected.** The model writing citation text (pages possibly invented, free text to parse).
**Limit.** Code proves a citation is a real retrieved chunk, not that it supports every claim. Phase 7 measured it: every answered question cited an expected source, and 4 of 46 answers (8.7%) at `top_k` 5, 3 of 47 at `top_k` 8, added a citation outside the expected list, mostly an older or shorter version of the same policy (E-4).

### D-33 · Refusal in three layers; no similarity threshold · Accepted (threshold rejected in Phase 7, E-4)
**Decision.** (1) No retrieved chunks: a fixed message, Gemini is not called. (2) The model answers `found: false`: no citations. (3) The model says `found: true` with no valid source number or a blank answer: replaced by a fixed "not found" message. No threshold; the similarities are logged.
**Why.** One corpus separates cleanly (answerable at 0.4968 or higher, refused at 0.4144 or lower); on the other a near-miss scored 0.6617, above every answerable question (E-1). One rule works on one corpus and fails on the other, and 14 manual questions cannot pick a number. The model's own `found` was right on all of them. Layer 3 is a safety net, not the main mechanism.
**Phase 7 result (E-4).** A threshold cannot separate: the near-miss q43 scores 0.657, above the lowest answerable question (0.382). The model's own `found` refused 5 of 5 at the baseline. **Revisit.** Only if a new corpus changes the scores.

### D-34 · `POST /api/v1/ask` · Accepted
**Decision.** Request `{question, top_k}` (same limits as `/search`), response `{answer, found, citations}`; `422` for bad input, `502` for Gemini failure. Thin plain `def` route; `RagServiceDep` reuses the shared retrieval and embedding objects.
**Why.** `/search` stays for inspection. `text` in a citation lets a UI show the quote. `found: false` is a field, not an error: "the documents do not say" is a normal result.

### D-35 · Logs hold numbers only · Accepted
**Decision.** Never log the question or chunk text. One `RAG:` line per question (chunk count, similarities, found, cited and dropped numbers) and one `Gemini call:` line (model, latency, finish reason, token counts).
**Why.** Logs outlive requests and are copied around. The numbers are what Phase 7 needed.

### D-36 · Free-tier data use decides which documents go to Gemini · Revisit at Phase 12
**Decision.** On the free tier only fictional, openly licensed or non-sensitive documents go through `/ask`. Ingestion, embeddings and `/search` run locally and send nothing out; only `/ask` calls Gemini.
**Why.** Google's terms (checked 2026-10): free-tier prompts and responses may be used to improve its products; paid tier not. `/ask` sends retrieved chunks.
**Revisit.** Phase 12: decide whether a paid key is needed for any real company document.

### D-37 · Tests never call Gemini · Accepted
**Decision.** Fake client for `LlmService`, plain chunks for the prompt, fake services for `RagService`, dependency overrides for the endpoint. The one real call is `scripts/smoke_gemini.py`, run by hand with a fictional café. The pre-commit scanner flagged a fake key in a test; fixed with an inline allow comment on that line. The evaluation runner (D-41) is tested the same way, with fakes.
**Why.** Real calls are slow, cost quota and fail with the network. The behaviour worth testing is ours: strict acceptance, refusal layers, dropped numbers, error mapping.

### D-38 · Test corpus: fictional policy documents · Accepted (storage location amended by D-40)
**Supersedes** the Docling Technical Report as the test corpus.
**Decision.** Three fictional German-company policy PDFs (workplace policies, smoke-free policy, working hours and vacation), then kept outside the repo (now in `data/corpus/`, D-40), are ingested. The Technical Report was deleted from the database (one `DELETE` naming its exact id; chunks cascade) and from MinIO. Eleven more policy PDFs waited for Phase 7 and were ingested then (D-41). No list or delete endpoint was added: a one-off cleanup does not justify code; reconsider if the UI needs it.
**Why.** Policy documents are what the product is for; they are fictional, so Gemini's free tier is safe; several overlap on purpose (smoking), which tests citation precision.
**Note.** Phase 3 to 5 measurements on the Technical Report stay valid as history.

---

## Process

### D-39 · Documentation system · Accepted (2026-10-13)
**Decision.** Four project docs, one question each: README (use), ROADMAP (plan and status, with a handoff block at the top), ARCHITECTURE (the system today, with invariants), DECISIONS (why, append-only with status). PROJECT.md holds scope. One fact has one home. Working rules live in a private cross-project kit loaded through the Project instructions. At the end of each phase: ripple check, update the four docs as complete files, one commit, tag.
**Why.** The old docs reached about 150 KB, copied the same facts into three or four files, and went stale (Phase 6 still "Next" after it was built). Docs are also context budget for the AI collaborator.
**Rejected.** One doc per phase (more files to keep consistent); patch scripts (against the "complete files" rule).

### D-40 · The fictional corpus is committed in `data/corpus/` · Accepted (2026-10-13)
**Amends** D-15 and D-38 (where the corpus lives).
**Decision.** The 14 policy PDFs of the fictional German company live in `data/corpus/` and are tracked by Git. `.gitignore` still ignores all other PDFs under `data/` and re-includes only `data/corpus/*.pdf`. `data/corpus/SOURCES.md` records the origin: generated by the repository owner with an AI assistant, fictional company, no real or third-party content.
**Why.** The owner generated the documents, so there is no third-party copyright question, and the repository is public. Anyone who clones it can reproduce the Phase 7 evaluation. The documents are fictional, so the Gemini free tier is acceptable for them (D-36).
**Rejected.** Keeping them outside the repo (the evaluation could not be reproduced); un-ignoring all of `data/` (the ISO standard and any downloaded third-party file must stay out).
**Revisit.** If any file turns out not to be the owner's own generated content: remove it from the repo and from `SOURCES.md`.

---

## Evaluation (Phase 7)

### D-41 · Evaluation design: separate retrieval and generation, correctness by hand · Accepted (2026-10-18)
**Decision.** The question set is `data/eval/questions.json` (version 5): 52 questions, 47 answerable and 5 to refuse, in kinds overlap 16, single passage 13, table 11, multi-passage 3, cross-language 4 (German, French, Spanish) and refusals (near-miss 3, not answerable 2). Each answerable question has expected facts (for hand review) and expected sources (file and pages; `any` or `all`). Retrieval is measured from one top-20 search per question (hit at 1, 3, 5, 10 and the answer size, and MRR). Generation is measured separately (answered, refused, citations cover the expected sources, padding, precision). Answer correctness is read by hand. Contradictions inside the corpus are tests on purpose (alcohol rule, referral bonus, sidewalk smoking, strength of the harassment consequence). The runner calls the services directly, writes the result file after every question, waits 5 seconds between Gemini calls (12 a minute under the 15 limit) and stops after 3 failures in a row. Scoring is pure code in `app/evaluation/`, so tests never call Gemini (I12).
**Why.** A wrong answer must be traceable to retrieval or to generation.
**Rejected.** Matching the expected facts literally in the chunk text: 92 of the expected facts do not appear word for word in any chunk, so it measured my wording (0 of 46 matched). Grading answers with a second LLM (more quota, an unmeasured judge). A refusal threshold (D-33, E-4).
**Limits.** Source matching is page-level: q07 counted a chunk on the right page that did not contain the answer. A qualified answer (q16, q24) is judged by hand, because the refusal metric only reads `found`.
**Revisit.** If the set grows, or if hand review becomes too slow: add short literal anchors per question.

### D-42 · Default `top_k` is 8 · Accepted (2026-10-18)
**Supersedes** the default of 5 in D-25. The limits (1 to 20) are unchanged.
**Decision.** `DEFAULT_TOP_K = 8` in `retrieval.py`.
**Why.** At 5, q07 (who is the Works Council chair) was refused: the contact tables of four files rank 6 to 9 (similarity 0.343 to 0.347, just below rank 5 at 0.351). At 8 it is answered correctly. Over all 52 questions (E-4): answered 46/47 to 47/47, mean citation precision 0.969 to 0.979, padded answers 4/46 to 3/47, mean citations 1.67 to 1.72. One question (q16) is flagged by the metric as wrongly answered, but its answer is the accepted one (no number, legal deadlines may apply, ask HR).
**Cost.** Up to 8 chunks in each prompt instead of 5.
**Rejected.** 10 (not tested, more tokens). Keeping 5 and merging contact chunks (a chunking change: re-ingest 14 files, about 18 minutes, new baseline; not needed).
**Revisit.** If token use or the free-tier limits matter, or if a larger corpus changes the picture.

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

On the Technical Report: a near-miss about a number the paper does not report scored 0.6617 (higher than every answerable question) and the model's `found: false` refused it. A French question retrieved the same chunk as the English one (0.5802 against 0.5792) and was answered in French. Gemini latency 0.6 to 1.1 s, about 1,000 to 1,400 prompt tokens, 40 to 120 output tokens. Ingestion of the three policy PDFs: 21, 11, 32 chunks (pipeline 143, 108, 94 s; embeddings 45, 38, 80 s). These are a handful of questions, not an evaluation.

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

Identical to the Phase 4 hand check to four digits. Small gaps between the top hits do not mean a weak match; ranking quality was measured in Phase 7 (E-4). Three questions on one document are a smoke test, not evidence for a threshold.

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
