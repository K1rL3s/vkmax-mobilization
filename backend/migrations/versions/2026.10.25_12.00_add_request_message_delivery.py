"""add request message delivery and author seen at

Revision ID: 3c1f0e7a9b42
Revises: bc21d9960e8b
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3c1f0e7a9b42"
down_revision: str | None = "bc21d9960e8b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("author_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "request_messages",
        sa.Column(
            "delivery",
            postgresql.ENUM(
                "pending",
                "delivered",
                "failed",
                "muted",
                "bot_stopped",
                name="notice_status",
                create_type=False,
            ),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("request_messages", "delivery")
    op.drop_column("requests", "author_seen_at")
