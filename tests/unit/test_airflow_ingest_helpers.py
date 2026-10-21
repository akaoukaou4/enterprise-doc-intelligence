import importlib.util
import uuid
from pathlib import Path

import pytest

HELPERS_PATH = Path(__file__).resolve().parents[2] / "airflow" / "dags" / "ingest_helpers.py"
_spec = importlib.util.spec_from_file_location("ingest_helpers", HELPERS_PATH)
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)


def test_parse_returns_the_ids():
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    assert helpers.parse_claimed_ids(f'["{first}", "{second}"]') == [first, second]


def test_parse_accepts_an_empty_list():
    assert helpers.parse_claimed_ids("[]") == []


def test_parse_uses_the_last_json_line_and_ignores_noise():
    document_id = str(uuid.uuid4())
    raw = f'warning: something\n["{document_id}"]\n'
    assert helpers.parse_claimed_ids(raw) == [document_id]


def test_parse_rejects_text_without_a_list():
    with pytest.raises(ValueError):
        helpers.parse_claimed_ids("Reset 0 orphaned, claimed 0.")


def test_parse_rejects_an_invalid_id():
    with pytest.raises(ValueError):
        helpers.parse_claimed_ids('["not-a-uuid"]')


def test_parse_rejects_a_non_string_id():
    with pytest.raises(ValueError):
        helpers.parse_claimed_ids("[5]")


def test_ingest_command_runs_the_script_in_the_app_venv():
    document_id = str(uuid.uuid4())
    command = helpers.ingest_command(document_id)
    assert command.endswith(f"scripts.ingest_document {document_id}")
    assert "/opt/app-venv/bin/python" in command


def test_ingest_command_rejects_anything_that_is_not_a_uuid():
    with pytest.raises(ValueError):
        helpers.ingest_command("abc; rm -rf /")


def test_claim_command_contains_the_limit():
    assert helpers.claim_command(5).endswith("scripts.claim_documents --limit 5")
