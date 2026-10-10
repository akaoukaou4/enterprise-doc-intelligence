"""Gemini access for answer generation.

This is the only module that imports the Google SDK. The rest of the application
sends text in and receives a validated Pydantic object out, so no SDK type leaks
into the RAG code and the SDK can be replaced by changing this file only.
"""

import logging
import time
from functools import lru_cache

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import ExternalServiceError

logger = logging.getLogger(__name__)

# The SDK takes the timeout in milliseconds.
REQUEST_TIMEOUT_MS = 30_000

# The cap includes thinking tokens, so it is generous: a cap that is too small
# cuts the JSON in half. A cut-off response is treated as an error, never parsed.
MAX_OUTPUT_TOKENS = 2048

# Messages shown to API clients. Details only go to the server log.
_NOT_CONFIGURED = "The AI service is not configured."
_BUSY = "The AI service is busy or its usage limit was reached. Try again later."
_FAILED = "The AI service request failed."
_UNUSABLE = "The AI service returned an unusable response."


@lru_cache(maxsize=1)
def _build_client(api_key: str) -> genai.Client:
    """Create the Gemini client once per process.

    attempts=1 means no retries: on the free tier a retry would use up the
    per-minute and per-day quota without helping. Failures are reported instead.
    """
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


class LlmService:
    """Ask Gemini a question and get a validated, structured answer back."""

    def __init__(self, settings: Settings, client: genai.Client | None = None) -> None:
        self._settings = settings
        self._model = settings.gemini_model
        # Built on first use, so the app and the tests start without a key.
        self._client = client

    def generate_structured[T: BaseModel](
        self,
        system_instruction: str,
        prompt: str,
        response_model: type[T],
    ) -> T:
        """Send one request and return the answer as a validated `response_model`.

        The schema is passed only in the config: describing the JSON in the prompt
        as well can lower output quality. Any failure becomes ExternalServiceError.
        """
        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_model,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

        started = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=config,
            )
        except errors.APIError as exc:
            logger.error("Gemini API error: code=%s message=%s", exc.code, exc.message)
            if exc.code == 429:
                raise ExternalServiceError(_BUSY) from exc
            raise ExternalServiceError(_FAILED) from exc
        except Exception as exc:  # network failure, timeout, ... (only this one call)
            logger.error("Gemini request failed: %s: %s", type(exc).__name__, exc)
            raise ExternalServiceError(_FAILED) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        candidates = response.candidates or []
        finish_reason = candidates[0].finish_reason if candidates else None
        usage = response.usage_metadata
        # Numbers only, never the question, the chunks or the answer text.
        logger.info(
            "Gemini call: model=%s latency_ms=%d finish_reason=%s "
            "prompt_tokens=%s output_tokens=%s thought_tokens=%s",
            self._model,
            latency_ms,
            getattr(finish_reason, "name", finish_reason),
            usage.prompt_token_count if usage else None,
            usage.candidates_token_count if usage else None,
            usage.thoughts_token_count if usage else None,
        )

        # Only a normally finished response is usable: blocked, cut-off or empty
        # output is never parsed.
        text = response.text
        if finish_reason != types.FinishReason.STOP or not text:
            logger.warning(
                "Gemini response not usable: finish_reason=%s has_text=%s",
                getattr(finish_reason, "name", finish_reason),
                bool(text),
            )
            raise ExternalServiceError(_UNUSABLE)

        try:
            return response_model.model_validate_json(text)
        except ValidationError as exc:
            # Error types only: the details would contain the model's output text.
            logger.warning(
                "Gemini output did not match %s: %s",
                response_model.__name__,
                [err["type"] for err in exc.errors(include_input=False)],
            )
            raise ExternalServiceError(_UNUSABLE) from exc

    def _get_client(self) -> genai.Client:
        if self._client is None:
            key = self._settings.gemini_api_key
            if key is None or not key.get_secret_value():
                logger.error("GEMINI_API_KEY is not set.")
                raise ExternalServiceError(_NOT_CONFIGURED)
            self._client = _build_client(key.get_secret_value())
        return self._client
