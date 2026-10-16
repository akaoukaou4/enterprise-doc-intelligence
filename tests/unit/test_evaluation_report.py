from app.evaluation.metrics import AnswerRecord, CitedRef, QuestionResult, summarize
from app.evaluation.questions import EvalQuestion, ExpectedSource
from app.evaluation.report import format_summary, render_review


def make_question(qid, found=True) -> EvalQuestion:
    return EvalQuestion(
        id=qid,
        question=f"What is {qid}?",
        language="en",
        kind="single_passage" if found else "not_answerable",
        expected_found=found,
        expected_facts=("Fact one",) if found else (),
        expected_sources=(ExpectedSource("a.pdf", (3,)),) if found else (),
        sources_match="any",
        notes="a note" if found else "",
    )


def make_result(qid, found=True, answer=None, error=None) -> QuestionResult:
    return QuestionResult(
        id=qid,
        kind="single_passage" if found else "not_answerable",
        language="en",
        expected_found=found,
        top_similarity=0.55,
        satisfied_rank=1 if found else None,
        retrieved=(),
        answer=answer,
        error=error,
    )


def test_summary_text_for_a_retrieval_only_run() -> None:
    summary = summarize([make_result("q1"), make_result("q2", found=False)], answer_k=5)

    text = format_summary(summary)

    assert "hit@5" in text
    assert "RETRIEVAL" in text
    assert "not run" in text
    assert text.isascii()


def test_summary_text_for_a_full_run() -> None:
    good = AnswerRecord(True, "x", (CitedRef("a.pdf", (3,), None, True),), True)
    wrong = AnswerRecord(True, "y", (CitedRef("b.pdf", (1,), None, False),), False)
    summary = summarize([make_result("q1", answer=good), make_result("q2", False, wrong)], 5)

    text = format_summary(summary)

    assert "wrongly answered: q2" in text
    assert "GENERATION" in text
    assert text.isascii()


def test_review_sheet_shows_question_facts_answer_and_citation_marks() -> None:
    questions = [make_question("q1"), make_question("q2", found=False)]
    cited = (
        CitedRef("a.pdf", (3,), "Shredding", True),
        CitedRef("b.pdf", (2, 3), None, False),
    )
    results = [
        make_result("q1", answer=AnswerRecord(True, "Line one\nLine two", cited, True)),
        make_result("q2", False, AnswerRecord(False, "Not found.", (), False)),
    ]

    text = render_review(questions, results, "run-1")

    assert "What is q1?" in text
    assert "- Fact one" in text
    assert "> Line one\n> Line two" in text
    assert "a.pdf p3 - Shredding (expected)" in text
    assert "b.pdf p2,3 (not in the expected list)" in text
    assert "a refusal" in text
    assert "a note" in text
    assert text.count("**Verdict:**") == 2


def test_review_sheet_shows_a_gemini_error() -> None:
    text = render_review(
        [make_question("q1")], [make_result("q1", error="ExternalServiceError: quota")], "r"
    )

    assert "No answer" in text
    assert "ExternalServiceError" in text
