"""add request deadline stamps

Revision ID: 3c1d9e7a52f0
Revises: 6f4b87d066b4
Create Date: 2026-09-29 10:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c1d9e7a52f0"
down_revision: str | None = "6f4b87d066b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("deadline_warned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("overdue_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE requests SET
            deadline_warned_at = now(),
            overdue_notified_at = CASE WHEN deadline_at <= now() THEN now() END
        WHERE deadline_at - greatest(
            least((deadline_at - created_at) / 4, interval '24 hours'),
            interval '1 hour'
        ) <= now()
        """,
    )


def downgrade() -> None:
    op.drop_column("requests", "overdue_notified_at")
    op.drop_column("requests", "deadline_warned_at")
