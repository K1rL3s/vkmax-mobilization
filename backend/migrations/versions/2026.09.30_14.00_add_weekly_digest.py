"""add weekly digest

Revision ID: 9c4b1f60d7a2
Revises: 5a2e7d41b0c6
Create Date: 2026-09-30 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c4b1f60d7a2"
down_revision: str | None = "5a2e7d41b0c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'digest'")
    op.add_column("houses", sa.Column("digest_sent_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("houses", "digest_sent_on")
    op.execute("DELETE FROM notification_settings WHERE category = 'digest'")
    op.execute("ALTER TYPE notification_category RENAME TO notification_category_old")
    op.execute(
        "CREATE TYPE notification_category AS ENUM "
        "('requests', 'announcements', 'meters')",
    )
    op.execute(
        "ALTER TABLE notification_settings ALTER COLUMN category TYPE "
        "notification_category USING category::text::notification_category",
    )
    op.execute("DROP TYPE notification_category_old")
