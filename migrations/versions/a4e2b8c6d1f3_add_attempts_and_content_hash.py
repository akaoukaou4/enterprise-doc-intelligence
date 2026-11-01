"""add attempts and content hash to documents

Revision ID: a4e2b8c6d1f3
Revises: 8c1d5e7a2b96
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4e2b8c6d1f3"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "8c1d5e7a2b96"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    # Nullable: documents uploaded before this migration have no hash.
    op.add_column("documents", sa.Column("content_sha256", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_documents_content_sha256", "documents", ["content_sha256"])


def downgrade() -> None:
    op.drop_constraint("uq_documents_content_sha256", "documents", type_="unique")
    op.drop_column("documents", "content_sha256")
    op.drop_column("documents", "attempts")
