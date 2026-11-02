# Enterprise AI Document Intelligence Platform

An internal knowledge assistant. Employees ask questions in natural language about company documents and get answers grounded in those documents, with citations to the source file, page and section. When the documents do not answer, the system says so instead of guessing.

> **Status:** work in progress. The current phase and the plan are in [ROADMAP.md](ROADMAP.md).
> **Unverified:** the Docker start below works on the author's machine, and the AWS steps were followed by the author only. Neither has been followed from a clean machine by someone else (ROADMAP, open questions).

## How it works

Upload PDF > Docling > HybridChunker > EmbeddingGemma > PostgreSQL + pgvector.
Question > closest chunks > Gemini > grounded answer with citations, or "not found".

Citations are built by code from the stored chunks; the model only says which numbered sources it used, so it cannot invent a page number. Ingestion starts by itself: an Airflow DAG picks up new documents and tracks their status. Details: [ARCHITECTURE.md](ARCHITECTURE.md). Why each choice was made: [DECISIONS.md](DECISIONS.md).

## Tech stack

| Area | Technology |
|---|---|
| Language / API | Python 3.12, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector, SQLAlchemy, Alembic |
| Object storage | MinIO locally, S3 on AWS (boto3) |
| Document processing | Docling, HybridChunker (CPU-only PyTorch) |
| AI | EmbeddingGemma (local embeddings), Gemini API (generation), RAG |
| Orchestration | Apache Airflow 3 (LocalExecutor) |
| UI | Streamlit (an HTTP client of the API) |
| Run | Docker Compose, one file for the whole system |
| Cloud | AWS: EC2, RDS PostgreSQL, S3, IAM, SSM |
| Infrastructure as code | Terraform (`infra/`) |
| Tooling | uv, Ruff, pytest, pre-commit, GitHub Actions |

## Quick start (Docker)

**You need:** Docker Desktop with at least 8 GB of memory for Docker, about 25 GB of free disk, internet for the first build, a free [Hugging Face](https://huggingface.co) account and a Gemini API key ([Google AI Studio](https://aistudio.google.com/apikey)).

1. Open https://huggingface.co/google/embeddinggemma-300m while logged in and accept the license (the model is gated). Create a token with read access in your Hugging Face settings.
2. Create your settings file (Windows PowerShell; on Linux or macOS use `cp`):

```powershell
copy .env.example .env
```

3. Edit `.env` and set the two required values: `HF_TOKEN` (used once, at build time, to put the model into the images; never stored in them) and `GEMINI_API_KEY` (needed for questions, not for ingestion). Everything else works as it is. Never commit `.env`.
4. Build and start everything:

```powershell
docker compose up -d --build
```

The first build downloads and bakes in the models: 30 to 90 minutes on a hard disk (one rebuild with a lost build cache took about 73 minutes on the author's laptop; about 4 minutes on the AWS instance's SSD), about 16 GB of images on the laptop. Later starts take seconds.

| Address | What |
|---|---|
| http://localhost:8501 | UI (upload, status, questions) |
| http://localhost:8000/docs | API docs. Health: `/health`, `/health/db`, `/health/model` |
| http://localhost:8080 | Airflow (login `airflow` / `airflow`, local use only) |
| http://localhost:9001 | MinIO console |

The embedding model loads in the background at start (about 30 s, longer on a cold disk); the UI status line shows "Model: ready" when questions can be answered.

**Stop and start again** (your documents stay):

```powershell
docker compose down
```

```powershell
docker compose up -d
```

`docker compose down -v` also deletes the database and the stored files. After any change to `app/`, `scripts/`, `airflow/dags/`, `pyproject.toml`, `uv.lock` or `Dockerfile`, run `docker compose up -d --build` again. After a change of `GEMINI_API_KEY` in `.env`, run `docker compose up -d`.

**Load the test corpus.** The database starts empty. A fictional corpus of 15 PDFs is in `data/corpus/` (14 policy documents of a fictional company, plus `Bicycle-Shed-Policy.pdf`, a short test document that contains an instruction aimed at the AI; origin: `data/corpus/SOURCES.md`). Upload them through the API; Airflow ingests one document at a time, about 3 to 4 minutes each, so the whole corpus takes about an hour (about 40 minutes on AWS). A file that is already stored is refused with `409`, so running this twice is harmless:

```powershell
Get-ChildItem data\corpus\*.pdf | ForEach-Object { curl.exe -s -F "file=@$($_.FullName);type=application/pdf" http://localhost:8000/api/v1/documents }
```

**Privacy.** On the free tier Google may use prompts and responses to improve its products. Upload and ask about only fictional, openly licensed or non-sensitive documents. Only questions call Gemini; ingestion, embeddings and search run locally. Details: [DECISIONS.md](DECISIONS.md) (D-28, D-36), `docs/provider_limits.md`.

## Usage

The UI covers upload, status and questions (file picker limit 20 MB, set in `.streamlit/config.toml`). The same calls are in the API docs.

**Upload.** `POST /api/v1/documents` (PDF only, up to 20 MB). If the same file content is already stored, the answer is `409` and names the existing document. **List and status.** `GET /api/v1/documents?limit=20&offset=0` (newest first), `GET /api/v1/documents/<id>`. The status moves on within about a minute:

| Status | Meaning |
|---|---|
| `uploaded` | stored, waiting for the next DAG run |
| `processing` | claimed, being converted, embedded and stored |
| `processed` | chunks are stored, the document can answer questions |
| `failed` | ingestion raised an error, or the document was claimed 3 times without finishing; not tried again by itself |

The reason for a failure is in the Airflow UI (DAG `ingest_documents`, the red run, task `ingest`, its log). To retry a failed document, set its status back to `uploaded` and its attempts to 0 (copy the id, do not type it):

```powershell
docker exec enterprise-doc-intelligence-postgres psql -U app -d enterprise_docs -c "update documents set status = 'uploaded', attempts = 0 where id = '<document_id>'"
```

**Delete.** `DELETE /api/v1/documents/<id>` removes the document, its chunks and its file (`204`; `404` unknown id; `409` while it is `processing`). There is no authentication in the app.

**Ask.** `POST /api/v1/ask` with `{"question": "How many vacation days do employees get per year?", "top_k": 8}`. `top_k` is optional (1 to 20, default 8). The response has `answer` (in the language of the question), `found` (`false` when the documents do not answer, with no citations) and `citations` (`filename`, `page_numbers`, `heading`, `document_id`, `text`). Bad input (an empty or too long question, `top_k` out of range) returns `422`. If Gemini is unreachable, out of quota or the key is missing, the API returns `502`; the reason is in the API log.

**Inspect retrieval without Gemini.** `POST /api/v1/search` returns the retrieved chunks and their similarity, best first: it shows whether a bad answer came from retrieval or from generation.

**Logs.** The API writes one line per request (method, path, status, time in milliseconds) with a request id; the same id is on every other log line of that request and in the `X-Request-ID` response header, so one question can be followed from the request to the Gemini call. Question text, answer text, chunk text and query strings are never logged. Read them with:

```powershell
docker compose logs api --tail 50
```

## Check the whole system

With the stack running and a Gemini key set, this uploads a fictional PDF (a copy of a corpus file with one comment line added, so it is not refused as a duplicate), waits for ingestion, checks search, one answer and one refusal, then deletes it. About 5 minutes and 2 Gemini requests. It needs [uv](https://docs.astral.sh/uv/) on the host; set `API_URL` to test another environment. It prints 10 PASS lines and `ALL CHECKS PASSED`.

```powershell
uv run python -m scripts.e2e_check
```

## AWS (Terraform)

The same compose and images run on one EC2 server, with RDS PostgreSQL (pgvector) and S3 instead of the local database and MinIO. The whole infrastructure is Terraform code in `infra/` (14 resources, including a $20 monthly budget with email alerts). **Nothing stays on AWS between sessions:** you apply, use it, and destroy it. Nothing is reachable from the internet: the server has no inbound rule, and you open the UI through an SSM tunnel.

You need Terraform 1.16 or newer, the AWS CLI with the Session Manager plugin, and an AWS account. Secrets reach Terraform only as environment variables set in your terminal (never in a file); the state file is local and holds the database password, so never commit or share it. In PowerShell, from the project folder:

```powershell
aws login
```

```powershell
terraform -chdir=infra init
```

```powershell
$env:TF_VAR_rds_password = [System.Net.NetworkCredential]::new("", (Read-Host "RDS password (12+ letters and digits)" -AsSecureString)).Password
```

```powershell
$env:TF_VAR_budget_email = [System.Net.NetworkCredential]::new("", (Read-Host "Budget email" -AsSecureString)).Password
```

Look at the plan before applying (the first time on a new machine, and after any change to `infra/`):

```powershell
terraform -chdir=infra plan
```

```powershell
terraform -chdir=infra apply
```

Then follow the rebuild steps in [ARCHITECTURE.md](ARCHITECTURE.md) section 12.3 (clone on the server, write its `.env`, build, start, run the check, open the tunnel). Logs on the server are read with `docker compose logs api` in the server session; there is no CloudWatch yet. When done:

```powershell
terraform -chdir=infra destroy
```

The reasons are in [DECISIONS.md](DECISIONS.md) (D-55 to D-61). The AWS account is on the Free plan, which ends on 2027-04-29. Phases 12 and 13 together cost about $1 of credits (E-9). `force_destroy` on the bucket and `skip_final_snapshot` on the database are safe only for the fictional corpus; remove both before any real data.

## Develop outside Docker

For changing the code with fast reloads. Needs Python 3.12 and uv. Free the ports first, and start only the storage containers:

```powershell
docker compose stop api ui
```

```powershell
uv sync
```

```powershell
uv run hf auth login
```

```powershell
docker compose up -d postgres minio minio-init
```

```powershell
uv run alembic upgrade head
```

```powershell
uv run uvicorn app.main:app --no-access-log
```

```powershell
uv run --group ui streamlit run ui/app.py
```

The host uses the localhost values in `.env`; set `PRELOAD_EMBEDDING_MODEL=true` there (turn it off while using `--reload`, which reloads the model on every save). `--no-access-log` switches off uvicorn's own request line, which would repeat the query string; the application's request log replaces it. Optional on Windows: keep large downloads off C: by setting `UV_CACHE_DIR` and `HF_HOME` to a folder on another drive. If you also use VMware, note that Docker needs Virtual Machine Platform and Windows Hypervisor Platform turned on in Windows features.

## Evaluate

A 53-question set (`data/eval/questions.json`, version 6) and a runner. It runs on the host (see above), with PostgreSQL running and the corpus ingested. Results go to `data/eval/runs/` (git-ignored); a full run also writes a `.review.md` for hand review. Kept results: [DECISIONS.md](DECISIONS.md) (E-4, E-9). A full run uses about 53 of the 500 free Gemini requests of a day. `q53` is a prompt-injection case: the runner does not check it, so read its entry in the `.review.md`.

```powershell
uv run python -m scripts.evaluate --retrieval-only
```

```powershell
uv run python -m scripts.evaluate --label mytest
```

To rerun a few questions only (for example to see whether a result is noise), add `--only q05,q26`.

## Development checks

Run before every push (the pre-push hook runs it too). Start the containers first, or the integration tests skip:

```powershell
docker compose up -d postgres minio minio-init
```

```powershell
.\scripts\check.ps1
```

The check runs Ruff (lint and format), the tests, and, when Terraform is installed, `terraform fmt -check`, `init -backend=false` and `validate` (without Terraform it prints a warning and skips them). Unit tests use fakes: no Docling or model, no database, and they never call Gemini. Integration tests (`tests/integration/`) use the real PostgreSQL and MinIO and skip themselves when unavailable. CI runs the same lint, format, test and Terraform checks, but does not build the Docker images (the gated model needs a token); the images and the deployment are checked by the end-to-end script. The Streamlit screens are checked by hand. `docker-compose.aws.yml` uses the Compose tags `!reset` and `!override`, so the YAML check in pre-commit runs in its syntax-only mode. `.gitattributes` keeps shell scripts on Unix line endings.

## Known limitations

* **Resources:** the whole system needs about 2.4 GB of memory at idle and about 7 GB during one ingestion, on the laptop and on the 8 GiB AWS instance alike. The margin is thin (on AWS the peak used the swap file): close heavy applications while a document is processed, and ingest one document at a time.
* **Access:** the app has no authentication. Locally, anyone who can reach the ports can upload and delete, and the Airflow login is the default. On AWS the network closes the access instead (no public port), so a demo for other people is a recording, not a link.
* Text and tables inside images are unreliable; a table can lose its header row or split across chunks. Some headings are wrong or missing, so the page number is the most reliable part of a citation.
* No similarity threshold: the model decides when to answer "not found", and a code check rejects answers without a valid citation. On the evaluation set it refused every question the documents cannot answer except one (q16), which was accepted by hand.
* An answer can be correct but incomplete: in the hand review of the baseline, 10 of 47 answers missed a required detail (E-4). Some answers cite one extra source that is not on the expected list; how often varies between runs (E-9).
* Prompt injection: one test document and one question show the model ignoring an instruction hidden in a document. That is one case, not a full defense.
* Duplicate uploads are refused by file content only for documents uploaded since Phase 14; the 14 older ones have no stored hash, so a second copy of one of them would still be accepted. The same text in a different file is not detected.
* Ingestion starts up to a minute after upload, and only while Airflow runs. A `failed` document shows only its status; the reason is in the Airflow log. A document that kills the worker is tried 3 times, then marked `failed`.
* Terraform: the state is local to one machine, and the code was applied from that machine only. The server's subnet is the first of the sorted default-VPC list; this was not checked with a plan yet.
* No CloudWatch logs or alarms: on AWS the logs are read in a server session.

Evaluation results and open items: [DECISIONS.md](DECISIONS.md) (E-4 to E-9) and the backlog in [ROADMAP.md](ROADMAP.md).

## Documentation

* [PROJECT.md](PROJECT.md): product definition and V1 scope
* [ARCHITECTURE.md](ARCHITECTURE.md): how the system works today, including the AWS rebuild steps
* [DECISIONS.md](DECISIONS.md): why each choice was made
* [ROADMAP.md](ROADMAP.md): plan and progress
* [airflow/README.md](airflow/README.md): the Airflow image and the DAG
