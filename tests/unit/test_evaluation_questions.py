import json
from pathlib import Path

import pytest

from app.evaluation.questions import parse_questions

QUESTION_FILE = Path(__file__).resolve().parents[2] / "data" / "eval" / "questions.json"


def answerable(**overrides):
    item = {
        "id": "q01",
        "question": "Where do documents go?",
        "language": "en",
        "kind": "single_passage",
        "expected_found": True,
        "expected_facts": ["Shred them"],
        "expected_sources": [{"file": "a.pdf", "pages": [3]}],
        "sources_match": "any",
        "notes": "why",
    }
    item.update(overrides)
    return item


def refusal(**overrides):
    item = answerable(
        id="q02",
        kind="not_answerable",
        expected_found=False,
        expected_facts=[],
        expected_sources=[],
    )
    item.update(overrides)
    return item


def test_parses_an_answerable_question() -> None:
    [question] = parse_questions({"questions": [answerable()]})

    assert question.id == "q01"
    assert question.expected_found is True
    assert question.expected_sources[0].file == "a.pdf"
    assert question.expected_sources[0].pages == (3,)
    assert question.notes == "why"


def test_notes_are_optional() -> None:
    item = answerable()
    del item["notes"]

    [question] = parse_questions({"questions": [item]})

    assert question.notes == ""


def test_parses_a_question_to_refuse() -> None:
    [question] = parse_questions({"questions": [refusal()]})

    assert question.expected_found is False
    assert question.expected_sources == ()


def test_rejects_a_missing_field() -> None:
    item = answerable()
    del item["kind"]

    with pytest.raises(ValueError, match="missing fields"):
        parse_questions({"questions": [item]})


@pytest.mark.parametrize(
    "bad",
    [
        answerable(kind="made_up"),
        answerable(sources_match="some"),
        answerable(question="   "),
        answerable(expected_sources=[]),
        answerable(expected_facts=[]),
        answerable(kind="near_miss"),
        answerable(sources_match="all"),
        answerable(expected_sources=[{"file": "a.pdf", "pages": [0]}]),
        answerable(expected_sources=[{"file": "a.pdf", "pages": []}]),
        refusal(expected_sources=[{"file": "a.pdf", "pages": [1]}]),
        refusal(expected_facts=["something"]),
    ],
)
def test_rejects_questions_that_break_the_rules(bad) -> None:
    with pytest.raises(ValueError):
        parse_questions({"questions": [bad]})


def test_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        parse_questions({"questions": [answerable(), answerable()]})


def test_rejects_an_empty_file() -> None:
    with pytest.raises(ValueError, match="no questions"):
        parse_questions({"questions": []})


def test_committed_question_file_is_valid() -> None:
    data = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))

    questions = parse_questions(data)

    assert any(question.expected_found for question in questions)
    assert any(not question.expected_found for question in questions)
