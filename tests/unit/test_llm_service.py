import pytest
from google.genai import errors, types
from pydantic import BaseModel, SecretStr

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.services import llm as llm_module
from app.services.llm import MAX_OUTPUT_TOKENS, REQUEST_TIMEOUT_MS, LlmService

SYSTEM = "Answer only from the sources."
PROMPT = "Question: what is Docling?"


class Reply(BaseModel):
    found: bool
    answer: str
    source_numbers: list[int]


GOOD_JSON = '{"found": true, "answer": "A document converter.", "source_numbers": [1, 2]}'


def make_settings(**overrides) -> Settings:
    values = {"gemini_api_key": SecretStr("test-key"), "gemini_model": "test-model"}
    values.update(overrides)
    # _env_file=None: the tests must not read the developer's local .env file.
    return Settings(_env_file=None, **values)


def response_with(
    text: str, finish_reason: types.FinishReason = types.FinishReason.STOP
) -> types.GenerateContentResponse:
    """A real SDK response object, so the service reads real attributes."""
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]),
                finish_reason=finish_reason,
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=10,
            candidates_token_count=5,
            thoughts_token_count=0,
        ),
    )


class FakeModels:
    """Stands in for client.models: records the call, then returns or raises."""

    def __init__(self, outcome) -> None:
        self._outcome = outcome
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class FakeClient:
    def __init__(self, outcome) -> None:
        self.models = FakeModels(outcome)


def make_service(outcome) -> tuple[LlmService, FakeClient]:
    client = FakeClient(outcome)
    return LlmService(make_settings(), client=client), client


def test_returns_validated_object_and_sends_expected_request() -> None:
    service, client = make_service(response_with(GOOD_JSON))

    result = service.generate_structured(SYSTEM, PROMPT, Reply)

    assert result == Reply(found=True, answer="A document converter.", source_numbers=[1, 2])
    assert len(client.models.calls) == 1
    call = client.models.calls[0]
    assert call["model"] == "test-model"
    assert call["contents"] == PROMPT
    config = call["config"]
    assert SYSTEM in str(config.system_instruction)
    assert config.response_mime_type == "application/json"
    assert config.response_schema is not None
    assert config.max_output_tokens == MAX_OUTPUT_TOKENS


def test_missing_api_key_is_reported_without_calling_gemini() -> None:
    service = LlmService(make_settings(gemini_api_key=None))

    with pytest.raises(ExternalServiceError, match="not configured"):
        service.generate_structured(SYSTEM, PROMPT, Reply)


def test_rate_limit_gets_a_busy_message() -> None:
    error = errors.ClientError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    service, _ = make_service(error)

    with pytest.raises(ExternalServiceError, match="busy"):
        service.generate_structured(SYSTEM, PROMPT, Reply)


def test_other_api_errors_get_a_generic_message_without_details() -> None:
    error = errors.ServerError(
        500, {"error": {"code": 500, "message": "internal secret detail", "status": "INTERNAL"}}
    )
    service, _ = make_service(error)

    with pytest.raises(ExternalServiceError, match="request failed") as exc_info:
        service.generate_structured(SYSTEM, PROMPT, Reply)

    assert "secret" not in exc_info.value.message


def test_unexpected_errors_become_external_errors_without_details() -> None:
    service, _ = make_service(TimeoutError("connection details"))

    with pytest.raises(ExternalServiceError, match="request failed") as exc_info:
        service.generate_structured(SYSTEM, PROMPT, Reply)

    assert "connection details" not in exc_info.value.message


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(types.GenerateContentResponse(candidates=[]), id="no_candidates"),
        pytest.param(response_with(""), id="empty_text"),
        pytest.param(
            response_with('{"found": true, "answer": "cut', types.FinishReason.MAX_TOKENS),
            id="cut_off",
        ),
        pytest.param(response_with("", types.FinishReason.SAFETY), id="blocked"),
        pytest.param(response_with("not json"), id="invalid_json"),
        pytest.param(response_with('{"found": true}'), id="missing_fields"),
        pytest.param(
            response_with('{"found": "maybe", "answer": "x", "source_numbers": []}'),
            id="wrong_type",
        ),
    ],
)
def test_unusable_responses_are_rejected(response) -> None:
    service, _ = make_service(response)

    with pytest.raises(ExternalServiceError, match="unusable"):
        service.generate_structured(SYSTEM, PROMPT, Reply)


def test_client_is_built_with_a_timeout_and_no_retries(monkeypatch) -> None:
    captured: dict = {}

    class RecordingClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    llm_module._build_client.cache_clear()
    monkeypatch.setattr(llm_module.genai, "Client", RecordingClient)
    try:
        llm_module._build_client("secret-key")
    finally:
        llm_module._build_client.cache_clear()

    assert captured["api_key"] == "secret-key"  # pragma: allowlist secret
    options = captured["http_options"]
    assert options.timeout == REQUEST_TIMEOUT_MS
    assert options.retry_options.attempts == 1
