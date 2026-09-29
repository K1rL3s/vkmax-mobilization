"""add request question stamps

Revision ID: c2898f019ff9
Revises: 7179b6991683
Create Date: 2026-09-30 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2898f019ff9"
down_revision: str | None = "7179b6991683"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("question_asked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("resident_answered_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("requests", "resident_answered_at")
    op.drop_column("requests", "question_asked_at")
