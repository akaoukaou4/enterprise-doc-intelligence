"""Ingest uploaded documents (Phase 8).

Every minute: claim the documents waiting for ingestion, then ingest them one at a
time. All logic lives in the app (scripts/claim_documents.py and
scripts/ingest_document.py, which record documents.status); this file only orchestrates.
"""

from datetime import timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag, task
from ingest_helpers import claim_command, ingest_command, parse_claimed_ids

CLAIM_LIMIT = 5


@dag(
    dag_id="ingest_documents",
    schedule="* * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["ingestion"],
)
def ingest_documents():
    claim = BashOperator(task_id="claim", bash_command=claim_command(CLAIM_LIMIT))

    @task
    def build_commands(raw: str) -> list[str]:
        return [ingest_command(document_id) for document_id in parse_claimed_ids(raw)]

    # One task per claimed document, one at a time (an ingestion peaks near 5 GiB).
    # No claimed documents -> no mapped tasks -> the run ends green.
    BashOperator.partial(
        task_id="ingest",
        max_active_tis_per_dag=1,
        retries=1,
        retry_delay=timedelta(minutes=1),
        execution_timeout=timedelta(minutes=45),
    ).expand(bash_command=build_commands(claim.output))


ingest_documents()
