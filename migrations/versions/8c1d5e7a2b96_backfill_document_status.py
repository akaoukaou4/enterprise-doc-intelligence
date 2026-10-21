"""backfill document status

Documents ingested before the status lifecycle existed still say 'uploaded'.
Every document that already has chunks becomes 'processed'.

Revision ID: 8c1d5e7a2b96
Revises: 3f9a7c2d1e84
Create Date: 2026-10-20
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8c1d5e7a2b96"  # pragma: allowlist secret
down_revision: str | None = "3f9a7c2d1e84"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE documents SET status = 'processed'
        WHERE status = 'uploaded'
          AND EXISTS (SELECT 1 FROM document_chunks c WHERE c.document_id = documents.id)
        """
    )


def downgrade() -> None:
    op.execute("UPDATE documents SET status = 'uploaded' WHERE status = 'processed'")
