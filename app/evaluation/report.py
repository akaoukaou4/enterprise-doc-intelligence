"""Readable output of a run: a console summary and a review sheet for hand checking.

Plain ASCII in the console text (Windows PowerShell can fail on other characters).
Question text is never printed to the console; ids and numbers only (I9).
"""

from collections.abc import Sequence
from typing import Any

from app.evaluation.metrics import QuestionResult
from app.evaluation.questions import EvalQuestion


def _pct(block: dict[str, Any]) -> str:
    rate = block["rate"]
    shown = "n/a" if rate is None else f"{rate * 100:.1f}%"
    return f"{block['count']}/{block['total']}  {shown}"


def _range(stats: dict[str, float] | None) -> str:
    if stats is None:
        return "n/a"
    return f"min {stats['min']:.4f}  mean {stats['mean']:.4f}  max {stats['max']:.4f}"


def format_summary(summary: dict[str, Any]) -> str:
    retrieval = summary["retrieval"]
    similarity = summary["similarity"]
    lines = [
        f"Questions run: {summary['questions_run']} "
        f"({summary['answerable']} answerable, {summary['to_refuse']} to refuse)",
        f"Errors: {len(summary['errors'])} {summary['errors'] or ''}".rstrip(),
        "",
        f"RETRIEVAL (answerable questions; the system answers with top_k={retrieval['answer_k']})",
    ]
    for k, block in retrieval["hit_at"].items():
        lines.append(f"  hit@{k:<3} {_pct(block)}")
    lines.append(f"  MRR     {retrieval['mrr']}")
    lines.append(f"  hit@{retrieval['answer_k']} by kind:")
    for kind, block in retrieval["hit_at_answer_k_by_kind"].items():
        lines.append(f"    {kind:<16} {_pct(block)}")
    missed = " ".join(retrieval["missed_at_answer_k"]) or "none"
    lines.append(f"  missed at {retrieval['answer_k']}: {missed}")

    lines += [
        "",
        "TOP SIMILARITY",
        f"  answerable: {_range(similarity['answerable'])}",
        f"  to refuse:  {_range(similarity['refusal'])}",
        f"  a threshold would separate them: {similarity['threshold_would_separate']}",
    ]

    generation = summary["generation"]
    if generation is None:
        lines += ["", "GENERATION: not run (retrieval-only)"]
        return "\n".join(lines)

    citations = generation["citations"]
    lines += [
        "",
        f"GENERATION ({generation['questions_with_model_answer']} answers from the model)",
        f"  answered when answerable:   {_pct(generation['answered_when_answerable'])}",
        f"  refused when unanswerable:  {_pct(generation['refused_when_unanswerable'])}",
        f"  wrongly refused:  {' '.join(generation['wrongly_refused']) or 'none'}",
        f"  wrongly answered: {' '.join(generation['wrongly_answered']) or 'none'}",
        f"  citations cover the expected sources: {_pct(citations['sources_satisfied'])}",
        f"  answers with padding (a citation not in the expected list): "
        f"{_pct(citations['with_padding'])}",
        f"  mean citation precision: {citations['mean_precision']}   "
        f"mean citations per answer: {citations['mean_citations']}",
        "",
        "Answer correctness is not measured automatically: read the review file.",
    ]
    return "\n".join(lines)


def _sources_text(question: EvalQuestion) -> str:
    if not question.expected_sources:
        return "none (the system must refuse)"
    joined = "; ".join(
        f"{source.file} p{','.join(str(page) for page in source.pages)}"
        for source in question.expected_sources
    )
    return f"{joined} (match: {question.sources_match})"


def render_review(
    questions: Sequence[EvalQuestion], results: Sequence[QuestionResult], title: str
) -> str:
    """A markdown sheet to check answers by hand, one section per question."""
    by_id = {question.id: question for question in questions}
    parts = [
        f"# Review: {title}",
        "",
        "For each answer, decide: correct, partial or wrong. Citations marked 'not in the "
        "expected list' are not automatically wrong: check whether the page really supports "
        "the answer.",
        "",
    ]
    for result in results:
        question = by_id[result.id]
        parts.append(f"### {question.id} - {question.kind} - {question.language}")
        parts.append(f"**Question:** {question.question}")
        parts.append("")
        if question.expected_found:
            parts.append("**Expected facts:**")
            parts += [f"- {fact}" for fact in question.expected_facts]
            parts.append("")
        else:
            parts.append("**Expected:** a refusal (the documents do not answer this).")
            parts.append("")
        parts.append(f"**Expected sources:** {_sources_text(question)}")
        parts.append("")

        if result.error:
            parts.append(f"**No answer:** {result.error}")
        elif result.answer is not None:
            answer = result.answer
            parts.append(
                f"**Model: found={answer.found}** (expected found={question.expected_found})"
            )
            parts.append("> " + answer.text.replace("\n", "\n> "))
            parts.append("")
            if answer.citations:
                parts.append("**Citations:**")
                for citation in answer.citations:
                    pages = ",".join(str(page) for page in citation.page_numbers)
                    mark = "expected" if citation.matches_expected else "not in the expected list"
                    section = f" - {citation.heading}" if citation.heading else ""
                    parts.append(f"- {citation.filename} p{pages}{section} ({mark})")
            else:
                parts.append("**Citations:** none")
        if question.notes:
            parts += ["", f"*Note:* {question.notes}"]
        parts += ["", "**Verdict:** ", "", "---", ""]
    return "\n".join(parts)
