"""Run the evaluation question set against the real system (Phase 7, step 3).

    uv run python -m scripts.evaluate --retrieval-only    # no Gemini calls, about 2 minutes
    uv run python -m scripts.evaluate                     # full run: also asks Gemini (paced)
    uv run python -m scripts.evaluate --label baseline    # adds a label to the file name
    uv run python -m scripts.evaluate --only q01,q05      # a few questions, for debugging

Writes data/eval/runs/<time>-<mode>[-label].json (every question, every number; rewritten
after each question so a stop loses nothing) and, in full mode, a .review.md sheet to
check the answers by hand. `runs/` is git-ignored: move a run you want to keep into
data/eval/results/.

Retrieval only reads PostgreSQL and uses the local embedding model. Full mode makes one
Gemini call per question, paced under the free-tier limit. Only fictional documents are
involved (I13). The console shows ids and numbers, never question text (I9).
"""

import argparse
import json
import re
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import DocumentChunk
from app.db.session import get_session_factory
from app.evaluation.metrics import QuestionResult, summarize
from app.evaluation.questions import EvalQuestion, parse_questions
from app.evaluation.report import format_summary, render_review
from app.evaluation.runner import MIN_SECONDS_BETWEEN_CALLS, SEARCH_K, run_evaluation
from app.services.embeddings import EmbeddingService
from app.services.llm import LlmService
from app.services.rag import RagService
from app.services.retrieval import DEFAULT_TOP_K, RetrievalService

DEFAULT_QUESTIONS = Path("data/eval/questions.json")
DEFAULT_OUT_DIR = Path("data/eval/runs")


def git_state() -> str:
    """Short commit id of the code that produced the run, '+dirty' if it has local changes."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit}+dirty" if dirty else commit


def select_questions(all_questions: list[EvalQuestion], only: str | None) -> list[EvalQuestion]:
    if not only:
        return all_questions
    wanted = [part.strip() for part in only.split(",") if part.strip()]
    known = {question.id for question in all_questions}
    unknown = [name for name in wanted if name not in known]
    if unknown:
        raise SystemExit(f"Unknown question ids: {unknown}")
    return [question for question in all_questions if question.id in wanted]


def write_run(path: Path, meta: dict[str, Any], results: list[QuestionResult]) -> dict[str, Any]:
    summary = summarize(results, DEFAULT_TOP_K)
    document = {"run": meta, "summary": summary, "results": [asdict(r) for r in results]}
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def progress_line(number: int, total: int, result: QuestionResult) -> str:
    parts = [f"[{number}/{total}] {result.id}"]
    if result.expected_found:
        parts.append(f"rank={result.satisfied_rank if result.satisfied_rank else '-'}")
    else:
        parts.append("to-refuse")
    parts.append(f"top_sim={result.top_similarity}")
    if result.error:
        parts.append(f"ERROR {result.error}")
    elif result.answer is not None:
        parts.append(f"found={result.answer.found} cited={len(result.answer.citations)}")
    return "  ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the evaluation question set.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--retrieval-only", action="store_true", help="skip Gemini")
    parser.add_argument("--label", help="added to the file name, for example baseline")
    parser.add_argument("--only", help="comma-separated question ids")
    args = parser.parse_args()

    if args.label and not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        raise SystemExit("--label may contain only letters, digits, '-' and '_'.")

    data = json.loads(args.questions.read_text(encoding="utf-8"))
    questions = select_questions(parse_questions(data), args.only)

    settings = get_settings()
    mode = "retrieval-only" if args.retrieval_only else "full"
    started = datetime.now(UTC)
    name = f"{started:%Y%m%d-%H%M%S}-{mode}" + (f"-{args.label}" if args.label else "")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    run_path = args.out_dir / f"{name}.json"

    results: list[QuestionResult] = []

    with get_session_factory()() as db:
        chunk_count = db.scalar(select(func.count()).select_from(DocumentChunk))
        meta = {
            "name": name,
            "started_utc": started.isoformat(timespec="seconds"),
            "mode": mode,
            "label": args.label,
            "question_file": str(args.questions),
            "questions": len(questions),
            "chunks_in_database": chunk_count,
            "search_k": SEARCH_K,
            "answer_top_k": DEFAULT_TOP_K,
            "embedding_model": settings.embedding_model_id,
            "gemini_model": None if args.retrieval_only else settings.gemini_model,
            "seconds_between_gemini_calls": (
                None if args.retrieval_only else MIN_SECONDS_BETWEEN_CALLS
            ),
            "git": git_state(),
        }
        print(f"Run {name}: {len(questions)} questions, {chunk_count} chunks in the database")

        retrieval = RetrievalService(db, EmbeddingService(settings))
        rag = None if args.retrieval_only else RagService(retrieval, LlmService(settings))
        if rag is not None:
            expected_minutes = len(questions) * MIN_SECONDS_BETWEEN_CALLS / 60
            print(f"Full mode: about {expected_minutes:.0f} minutes (paced for the free tier)")
        print("The first question loads the embedding model (about 20 s).", flush=True)

        def on_result(result: QuestionResult) -> None:
            results.append(result)
            write_run(run_path, meta, results)
            print(progress_line(len(results), len(questions), result), flush=True)

        t0 = time.perf_counter()
        completed = run_evaluation(questions, retrieval, rag, on_result)
        elapsed = time.perf_counter() - t0

    summary = write_run(run_path, meta, results)
    print(f"\nFinished in {elapsed:.0f} s. Results: {run_path}")
    if not args.retrieval_only:
        review_path = run_path.with_suffix(".review.md")
        review_path.write_text(render_review(questions, results, name), encoding="utf-8")
        print(f"Review sheet: {review_path}")
    print()
    print(format_summary(summary))

    if not completed:
        print("\nSTOPPED EARLY after repeated Gemini failures (quota or outage?).")
        print("Results so far are saved. Check the daily quota in AI Studio before re-running.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
