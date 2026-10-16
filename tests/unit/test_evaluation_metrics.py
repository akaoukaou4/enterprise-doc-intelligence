from types import SimpleNamespace

from app.evaluation.metrics import (
    AnswerRecord,
    CitedRef,
    QuestionResult,
    is_expected_ref,
    satisfied_rank,
    source_matches,
    sources_satisfied,
    summarize,
)
from app.evaluation.questions import EvalQuestion, ExpectedSource


def make_question(sources, match="any", found=True) -> EvalQuestion:
    return EvalQuestion(
        id="q",
        question="?",
        language="en",
        kind="single_passage" if found else "not_answerable",
        expected_found=found,
        expected_facts=("fact",) if found else (),
        expected_sources=tuple(ExpectedSource(file, tuple(pages)) for file, pages in sources),
        sources_match=match,
        notes="",
    )


def ref(filename, pages):
    return SimpleNamespace(filename=filename, page_numbers=pages)


def test_source_matches_needs_same_file_and_a_shared_page() -> None:
    source = ExpectedSource("a.pdf", (3, 4))

    assert source_matches(source, ref("a.pdf", [4, 5]))
    assert not source_matches(source, ref("a.pdf", [5]))
    assert not source_matches(source, ref("b.pdf", [3]))


def test_any_needs_one_source_and_all_needs_every_source() -> None:
    sources = [("a.pdf", [5]), ("a.pdf", [6])]
    only_first = [ref("a.pdf", [5])]
    both = [ref("a.pdf", [5]), ref("a.pdf", [6])]

    assert sources_satisfied(make_question(sources, "any"), only_first)
    assert not sources_satisfied(make_question(sources, "all"), only_first)
    assert sources_satisfied(make_question(sources, "all"), both)


def test_one_chunk_spanning_both_pages_satisfies_all() -> None:
    question = make_question([("a.pdf", [5]), ("a.pdf", [6])], "all")

    assert sources_satisfied(question, [ref("a.pdf", [5, 6])])


def test_a_question_without_sources_is_never_satisfied() -> None:
    assert not sources_satisfied(make_question([], found=False), [ref("a.pdf", [1])])


def test_satisfied_rank_is_the_position_that_completes_the_sources() -> None:
    refs = [ref("x.pdf", [1]), ref("a.pdf", [5]), ref("y.pdf", [2]), ref("a.pdf", [6])]

    assert satisfied_rank(make_question([("a.pdf", [5])]), refs) == 2
    assert satisfied_rank(make_question([("a.pdf", [5]), ("a.pdf", [6])], "all"), refs) == 4
    assert satisfied_rank(make_question([("z.pdf", [1])]), refs) is None


def test_is_expected_ref() -> None:
    question = make_question([("a.pdf", [3])])

    assert is_expected_ref(question, ref("a.pdf", [3]))
    assert not is_expected_ref(question, ref("a.pdf", [9]))


def cited(matches: bool) -> CitedRef:
    return CitedRef("a.pdf", (1,), None, matches)


def result(qid, found, rank, top, answer=None, kind="single_passage") -> QuestionResult:
    return QuestionResult(
        id=qid,
        kind=kind,
        language="en",
        expected_found=found,
        top_similarity=top,
        satisfied_rank=rank,
        retrieved=(),
        answer=answer,
    )


def sample_results() -> list[QuestionResult]:
    return [
        result("q1", True, 1, 0.8, AnswerRecord(True, "a", (cited(True),), True)),
        result(
            "q2", True, 4, 0.6, AnswerRecord(True, "b", (cited(True), cited(False)), True), "table"
        ),
        result("q3", True, None, 0.5, AnswerRecord(False, "c", (), False)),
        result("q4", False, None, 0.4, AnswerRecord(False, "d", (), False), "not_answerable"),
        result(
            "q5", False, None, 0.7, AnswerRecord(True, "e", (cited(False),), False), "near_miss"
        ),
    ]


def test_summarize_retrieval() -> None:
    summary = summarize(sample_results(), answer_k=5)
    retrieval = summary["retrieval"]

    assert summary["answerable"] == 3
    assert summary["to_refuse"] == 2
    assert retrieval["hit_at"]["1"]["count"] == 1
    assert retrieval["hit_at"]["3"]["count"] == 1
    assert retrieval["hit_at"]["5"] == {"count": 2, "total": 3, "rate": 0.667}
    assert retrieval["mrr"] == 0.417  # (1 + 1/4 + 0) / 3
    assert retrieval["missed_at_answer_k"] == ["q3"]
    assert retrieval["hit_at_answer_k_by_kind"]["table"]["count"] == 1


def test_summarize_includes_the_answer_cutoff_even_when_unusual() -> None:
    summary = summarize(sample_results(), answer_k=7)

    assert "7" in summary["retrieval"]["hit_at"]


def test_summarize_similarity_and_threshold() -> None:
    similarity = summarize(sample_results(), answer_k=5)["similarity"]

    assert similarity["answerable"] == {"min": 0.5, "mean": 0.6333, "max": 0.8}
    assert similarity["refusal"]["max"] == 0.7
    assert similarity["threshold_would_separate"] is False  # q5 scores above q3

    separable = [
        result("a", True, 1, 0.6),
        result("r", False, None, 0.3, kind="not_answerable"),
    ]
    assert summarize(separable, 5)["similarity"]["threshold_would_separate"] is True


def test_summarize_generation() -> None:
    generation = summarize(sample_results(), answer_k=5)["generation"]

    assert generation["answered_when_answerable"] == {"count": 2, "total": 3, "rate": 0.667}
    assert generation["refused_when_unanswerable"]["count"] == 1
    assert generation["wrongly_refused"] == ["q3"]
    assert generation["wrongly_answered"] == ["q5"]
    assert generation["citations"]["answers_checked"] == 2
    assert generation["citations"]["with_padding"]["count"] == 1
    assert generation["citations"]["mean_precision"] == 0.75
    assert generation["citations"]["mean_citations"] == 1.5


def test_summarize_without_answers_has_no_generation_block() -> None:
    summary = summarize([result("q1", True, 1, 0.8)], answer_k=5)

    assert summary["generation"] is None
    assert summary["errors"] == []


def test_summarize_lists_questions_that_errored() -> None:
    failed = QuestionResult("q9", "table", "en", True, 0.5, 2, (), None, "ExternalServiceError: x")

    assert summarize([failed], 5)["errors"] == ["q9"]
