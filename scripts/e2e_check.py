"""End-to-end check of a running system, over HTTP only (Phase 10, plan item 2).

Flow: upload a fictional corpus PDF under a unique name, wait until it is
processed, check that search finds it, ask one answerable and one
unanswerable question, then delete the test document.

Needs: the API running with PRELOAD_EMBEDDING_MODEL=true, Airflow running with
the DAG unpaused, and a Gemini key. Costs 2 Gemini requests (free tier).
Only fictional documents are used (I13).

Run from the project root:
    uv run python -m scripts.e2e_check
Set API_URL to test another environment. Exit code 0 = all checks passed.
"""

import os
import sys
import time
import uuid
from pathlib import Path

import requests

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
BASE = f"{API_URL}/api/v1"

SOURCE_PDF = Path("data/corpus/Sample_Business_Dress_Code_Policy.pdf")
# Evaluation question q51 (answerable) and q17 (not answerable), see data/eval/questions.json.
ANSWERABLE_QUESTION = "Can I wear jeans on Casual Friday?"
REFUSAL_QUESTION = "What is the maximum fine for a GDPR violation?"

MODEL_TIMEOUT_S = 180  # the model loads in the background; cold disk can be slow
INGEST_TIMEOUT_S = 15 * 60  # about 4 minutes measured (E-5); the DAG polls every minute
POLL_S = 10
GEMINI_PAUSE_S = 5  # stays under the free-tier rate limit (D-41)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)
    return ok


def wait_for_model() -> bool:
    deadline = time.monotonic() + MODEL_TIMEOUT_S
    state = "unreachable"
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{API_URL}/health/model", timeout=5)
            state = response.json().get("status", "unknown")
            if response.status_code == 200:
                return check("embedding model ready", True)
        except requests.RequestException:
            state = "unreachable"
        time.sleep(3)
    return check(
        "embedding model ready",
        False,
        f"state {state}; set PRELOAD_EMBEDDING_MODEL=true in .env and restart the API",
    )


def wait_for_processed(document_id: str) -> bool:
    deadline = time.monotonic() + INGEST_TIMEOUT_S
    started = time.monotonic()
    last = ""
    while time.monotonic() < deadline:
        status = requests.get(f"{BASE}/documents/{document_id}", timeout=15).json()["status"]
        if status != last:
            print(f"      status {status} after {time.monotonic() - started:.0f} s")
            last = status
        if status == "processed":
            return check("document reaches processed", True)
        if status == "failed":
            return check("document reaches processed", False, "status failed; see Airflow log")
        time.sleep(POLL_S)
    return check("document reaches processed", False, f"timeout; last status {last}")


def ask(question: str) -> dict:
    response = requests.post(f"{BASE}/ask", json={"question": question, "top_k": 8}, timeout=90)
    response.raise_for_status()
    return response.json()


def run_checks(filename: str) -> None:
    hits = requests.post(
        f"{BASE}/search", json={"question": ANSWERABLE_QUESTION, "top_k": 8}, timeout=90
    ).json()["results"]
    check(
        "search finds the new document",
        filename in {hit["filename"] for hit in hits},
        f"{len(hits)} hits",
    )

    answer = ask(ANSWERABLE_QUESTION)
    check(
        "answerable question is answered with citations",
        answer["found"] is True and len(answer["citations"]) > 0,
        f"found={answer['found']}, citations={len(answer['citations'])}",
    )

    time.sleep(GEMINI_PAUSE_S)
    refusal = ask(REFUSAL_QUESTION)
    check(
        "unanswerable question is refused without citations",
        refusal["found"] is False and refusal["citations"] == [],
        f"found={refusal['found']}, citations={len(refusal['citations'])}",
    )


def cleanup(document_id: str, total_before: int) -> None:
    response = requests.delete(f"{BASE}/documents/{document_id}", timeout=30)
    if response.status_code == 409:
        check("test document deleted", False, f"still processing; delete {document_id} later")
        return
    if not check("test document deleted", response.status_code == 204, str(response.status_code)):
        return
    gone = requests.get(f"{BASE}/documents/{document_id}", timeout=15).status_code == 404
    check("deleted document is gone", gone)
    total_after = requests.get(f"{BASE}/documents?limit=1", timeout=15).json()["total"]
    check("document count is back to the start", total_after == total_before, str(total_after))


def main() -> int:
    if not SOURCE_PDF.exists():
        print(f"Missing {SOURCE_PDF}. Run from the project root.")
        return 1

    try:
        if not check("API reachable", requests.get(f"{API_URL}/health", timeout=5).ok):
            return 1
    except requests.RequestException:
        check("API reachable", False, API_URL)
        return 1

    if not wait_for_model():
        return 1

    total_before = requests.get(f"{BASE}/documents?limit=1", timeout=15).json()["total"]
    filename = f"e2e-{uuid.uuid4().hex[:8]}-{SOURCE_PDF.name}"
    upload = requests.post(
        f"{BASE}/documents",
        files={"file": (filename, SOURCE_PDF.read_bytes(), "application/pdf")},
        timeout=60,
    )
    if not check("upload returns 201", upload.status_code == 201, str(upload.status_code)):
        return 1
    document_id = upload.json()["id"]
    print(f"      document id {document_id}")

    try:
        if wait_for_processed(document_id):
            run_checks(filename)
    except (requests.RequestException, KeyError, ValueError) as error:
        check("script ran without an unexpected error", False, type(error).__name__)
    finally:
        cleanup(document_id, total_before)

    print("ALL CHECKS PASSED" if not failures else f"FAILED: {len(failures)} check(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
