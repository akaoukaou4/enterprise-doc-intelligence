"""Manual check: real Gemini calls through LlmService, with made-up sources only.

Never put a real document here. Each run uses 2 requests of the daily free quota.
Run from the project root:

    uv run python -m scripts.smoke_gemini
"""

import logging

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.services.llm import LlmService

SYSTEM = (
    "You answer questions using only the numbered sources provided. "
    "If the sources do not contain the answer, set found to false, leave source_numbers "
    "empty and say so in the answer. Otherwise set found to true and list the numbers of "
    "the sources you used."
)

SOURCES = """[1] Cafe Lumen opens at 8:00 in the morning on weekdays and at 10:00 on weekends.
[2] Cafe Lumen serves oat milk at no extra charge. Delivery is not offered."""

QUESTIONS = [
    "When does the cafe open on weekdays?",
    "How many employees does the cafe have?",
]


class Reply(BaseModel):
    found: bool
    answer: str
    source_numbers: list[int]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    service = LlmService(settings)
    print(f"model: {settings.gemini_model}")

    for question in QUESTIONS:
        print(f"\nQUESTION: {question}")
        prompt = f"Sources:\n{SOURCES}\n\nQuestion: {question}"
        try:
            reply = service.generate_structured(SYSTEM, prompt, Reply)
        except ExternalServiceError as exc:
            print(f"FAILED: {exc.message}")
            continue
        print(f"found: {reply.found}")
        print(f"answer: {reply.answer}")
        print(f"source_numbers: {reply.source_numbers}")


if __name__ == "__main__":
    main()
