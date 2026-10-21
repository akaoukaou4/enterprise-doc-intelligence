"""Pure helpers for the ingestion DAG (no Airflow imports, so unit tests can load them)."""

import json
import uuid

# The app runs in its own virtualenv. `env -u PYTHONPATH` keeps Airflow's packages out of it.
APP_RUN = "cd /opt/app && env -u PYTHONPATH /opt/app-venv/bin/python -m"


def claim_command(limit: int) -> str:
    return f"{APP_RUN} scripts.claim_documents --limit {int(limit)}"


def ingest_command(document_id: str) -> str:
    # uuid.UUID() rejects anything that is not a UUID, so nothing else reaches the shell.
    return f"{APP_RUN} scripts.ingest_document {uuid.UUID(document_id)}"


def parse_claimed_ids(raw: str) -> list[str]:
    """The ids printed by scripts.claim_documents: a JSON list on the last such line."""
    for line in reversed(raw.strip().splitlines()):
        line = line.strip()
        if line.startswith("["):
            items = json.loads(line)
            if not all(isinstance(item, str) for item in items):
                raise ValueError("claim_documents printed a non-string id")
            return [str(uuid.UUID(item)) for item in items]
    raise ValueError("claim_documents printed no JSON list")
