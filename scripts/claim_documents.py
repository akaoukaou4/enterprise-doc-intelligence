"""Claim the documents that wait for ingestion (used by the Airflow DAG).

    uv run python -m scripts.claim_documents [--limit N]

First turns documents left in 'processing' by a killed run back into 'uploaded',
then claims up to N 'uploaded' documents (they become 'processing'). The ids are
printed as one JSON list on the last line of stdout; the summary goes to stderr.

Run it only when no ingestion is running (the DAG allows one run at a time).
"""

import argparse
import json
import sys

from app.db.session import get_session_factory
from app.services.document_status import DocumentStatusService

DEFAULT_LIMIT = 10


def main() -> None:
    parser = argparse.ArgumentParser(description="Claim documents waiting for ingestion.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    with get_session_factory()() as db:
        statuses = DocumentStatusService(db)
        reset = statuses.reset_orphans()
        ids = statuses.claim_uploaded(args.limit)

    print(f"Reset {reset} orphaned, claimed {len(ids)}.", file=sys.stderr)
    print(json.dumps([str(document_id) for document_id in ids]))


if __name__ == "__main__":
    main()
