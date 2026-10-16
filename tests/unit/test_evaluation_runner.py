import uuid

import pytest

from app.core.errors import ExternalServiceError
from app.evaluation.questions import EvalQuestion, ExpectedSource
from app.evaluation.runner import (
    MAX_CONSECUTIVE_ERRORS,
    SEARCH_K,
    Pacer,
    evaluate_question,
    run_evaluation,
)
from app.services.rag import Citation, RagAnswer
from app.services.retrieval import RetrievedChunk


def make_question(qid="q1", found=True, file="a.pdf", pages=(3,)) -> EvalQuestion:
    return EvalQuestion(
        id=qid,
        question=f"question {qid}",
        language="en",
        kind="single_passage" if found else "not_answerable",
        expected_found=found,
        expected_facts=("fact",) if found else (),
        expected_sources=(ExpectedSource(file, pages),) if found else (),
        sources_match="any",
        notes="",
    )


def chunk(filename, pages, similarity=0.5) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        filename=filename,
        page_numbers=list(pages),
        heading=None,
        text="text",
        similarity=similarity,
    )


class FakeRetrieval:
    def __init__(self, chunks) -> None:
        self.chunks = chunks
        self.calls: list[int] = []

    def search(self, question, top_k):
        self.calls.append(top_k)
        return self.chunks


class FakeRag:
    def __init__(self, outcomes) -> None:
        self.outcomes = list(outcomes)
        self.asked: list[str] = []

    def ask(self, question):
        self.asked.append(question)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class CountingPacer(Pacer):
    def __init__(self) -> None:
        super().__init__(min_interval=0)
        self.waits = 0

    def wait(self) -> None:
        self.waits += 1


def answer(found=True, pages=(3,), filename="a.pdf") -> RagAnswer:
    citations = [Citation(uuid.uuid4(), filename, list(pages), "Heading", "text")] if found else []
    return RagAnswer(answer="the answer", found=found, citations=citations)


def test_retrieval_only_never_calls_the_model_or_the_pacer() -> None:
    retrieval = FakeRetrieval([chunk("x.pdf", [1], 0.9), chunk("a.pdf", [3], 0.7)])
    pacer = CountingPacer()

    result = evaluate_question(make_question(), retrieval, None, pacer)

    assert retrieval.calls == [SEARCH_K]
    assert pacer.waits == 0
    assert result.answer is None
    assert result.error is None
    assert result.satisfied_rank == 2
    assert result.top_similarity == 0.9
    assert [ref.matches_expected for ref in result.retrieved] == [False, True]


def test_full_mode_records_the_answer_and_checks_its_citations() -> None:
    retrieval = FakeRetrieval([chunk("a.pdf", [3])])
    rag = FakeRag([answer(pages=(3,))])
    pacer = CountingPacer()

    result = evaluate_question(make_question(), retrieval, rag, pacer)

    assert pacer.waits == 1
    assert rag.asked == ["question q1"]
    assert result.answer.found is True
    assert result.answer.text == "the answer"
    assert result.answer.sources_satisfied is True
    assert result.answer.citations[0].matches_expected is True


def test_a_citation_outside_the_expected_list_is_marked() -> None:
    retrieval = FakeRetrieval([chunk("a.pdf", [3])])
    rag = FakeRag([answer(pages=(9,))])

    result = evaluate_question(make_question(), retrieval, rag, CountingPacer())

    assert result.answer.citations[0].matches_expected is False
    assert result.answer.sources_satisfied is False


def test_a_question_to_refuse_has_no_rank() -> None:
    retrieval = FakeRetrieval([chunk("a.pdf", [3], 0.66)])
    rag = FakeRag([answer(found=False)])

    result = evaluate_question(make_question(found=False), retrieval, rag, CountingPacer())

    assert result.satisfied_rank is None
    assert result.top_similarity == 0.66
    assert result.answer.found is False


def test_a_gemini_failure_is_recorded_not_raised() -> None:
    retrieval = FakeRetrieval([chunk("a.pdf", [3])])
    rag = FakeRag([ExternalServiceError("quota")])

    result = evaluate_question(make_question(), retrieval, rag, CountingPacer())

    assert result.answer is None
    assert "ExternalServiceError" in result.error
    assert result.satisfied_rank == 1  # retrieval was still measured


def test_other_errors_are_not_swallowed() -> None:
    retrieval = FakeRetrieval([chunk("a.pdf", [3])])
    rag = FakeRag([RuntimeError("bug")])

    with pytest.raises(RuntimeError):
        evaluate_question(make_question(), retrieval, rag, CountingPacer())


def run(outcomes):
    questions = [make_question(f"q{i}") for i in range(len(outcomes))]
    retrieval = FakeRetrieval([chunk("a.pdf", [3])])
    results = []
    completed = run_evaluation(
        questions, retrieval, FakeRag(outcomes), results.append, CountingPacer()
    )
    return completed, results


def test_run_reports_every_result_in_order() -> None:
    completed, results = run([answer(), answer(), answer()])

    assert completed is True
    assert [r.id for r in results] == ["q0", "q1", "q2"]


def test_run_stops_after_repeated_failures() -> None:
    failure = ExternalServiceError("quota")
    completed, results = run([failure] * 6)

    assert completed is False
    assert len(results) == MAX_CONSECUTIVE_ERRORS


def test_a_success_resets_the_failure_count() -> None:
    failure = ExternalServiceError("x")
    completed, results = run([failure, failure, answer(), failure, failure, answer()])

    assert completed is True
    assert len(results) == 6


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def test_pacer_waits_only_for_the_remaining_time() -> None:
    clock = FakeClock()
    pacer = Pacer(min_interval=5.0, clock=clock.time, sleep=clock.sleep)

    pacer.wait()  # first call: no wait
    clock.now += 2.0  # the call took 2 seconds
    pacer.wait()  # must wait 3 more seconds
    clock.now += 10.0  # a slow call: no wait needed
    pacer.wait()

    assert clock.slept == [3.0]
