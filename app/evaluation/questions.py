"""The evaluation question set: typed objects and validation of data/eval/questions.json."""

from dataclasses import dataclass
from typing import Any

KINDS = frozenset(
    {
        "single_passage",
        "multi_passage",
        "table",
        "overlap",
        "cross_language",
        "near_miss",
        "not_answerable",
    }
)
MATCH_MODES = frozenset({"any", "all"})
# Questions of these kinds must be refused by the system.
REFUSAL_KINDS = frozenset({"near_miss", "not_answerable"})

_REQUIRED_FIELDS = (
    "id",
    "question",
    "language",
    "kind",
    "expected_found",
    "expected_facts",
    "expected_sources",
    "sources_match",
)


@dataclass(frozen=True)
class ExpectedSource:
    """An acceptable place for the answer. Several pages mean any of those pages."""

    file: str
    pages: tuple[int, ...]


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    language: str
    kind: str
    expected_found: bool
    expected_facts: tuple[str, ...]
    expected_sources: tuple[ExpectedSource, ...]
    sources_match: str
    notes: str


def parse_questions(data: dict[str, Any]) -> list[EvalQuestion]:
    """Turn the loaded JSON into questions, or raise ValueError naming the problem."""
    raw = data.get("questions")
    if not isinstance(raw, list) or not raw:
        raise ValueError("The question file contains no questions.")

    questions = [_parse_one(item) for item in raw]
    ids = [question.id for question in questions]
    duplicates = sorted({question_id for question_id in ids if ids.count(question_id) > 1})
    if duplicates:
        raise ValueError(f"Duplicate question ids: {duplicates}")
    return questions


def _parse_one(item: dict[str, Any]) -> EvalQuestion:
    missing = [name for name in _REQUIRED_FIELDS if name not in item]
    if missing:
        raise ValueError(f"Question {item.get('id', '?')} is missing fields: {missing}")

    question = EvalQuestion(
        id=item["id"],
        question=item["question"],
        language=item["language"],
        kind=item["kind"],
        expected_found=bool(item["expected_found"]),
        expected_facts=tuple(item["expected_facts"]),
        expected_sources=tuple(
            ExpectedSource(file=source["file"], pages=tuple(source["pages"]))
            for source in item["expected_sources"]
        ),
        sources_match=item["sources_match"],
        notes=item.get("notes", ""),
    )
    _check_rules(question)
    return question


def _check_rules(question: EvalQuestion) -> None:
    name = question.id
    if question.kind not in KINDS:
        raise ValueError(f"{name}: unknown kind {question.kind!r}")
    if question.sources_match not in MATCH_MODES:
        raise ValueError(f"{name}: sources_match must be 'any' or 'all'")
    if not question.question.strip():
        raise ValueError(f"{name}: the question text is empty")

    if question.expected_found:
        if question.kind in REFUSAL_KINDS:
            raise ValueError(f"{name}: kind {question.kind} must have expected_found=false")
        if not question.expected_facts or not question.expected_sources:
            raise ValueError(f"{name}: an answerable question needs facts and sources")
        if question.sources_match == "all" and len(question.expected_sources) < 2:
            raise ValueError(f"{name}: sources_match 'all' needs at least 2 sources")
    elif question.expected_facts or question.expected_sources:
        raise ValueError(f"{name}: a question to refuse must have no facts and no sources")

    for source in question.expected_sources:
        if not source.pages or any(page < 1 for page in source.pages):
            raise ValueError(f"{name}: pages of {source.file} must be 1 or higher")
