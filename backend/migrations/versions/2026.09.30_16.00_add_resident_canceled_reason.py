"""add resident_canceled completion reason

Revision ID: 7179b6991683
Revises: 8d2f4b61c7a9
Create Date: 2026-09-30 16:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "7179b6991683"
down_revision: str | None = "8d2f4b61c7a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE request_completion_reason "
        "ADD VALUE IF NOT EXISTS 'resident_canceled'",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE requests SET completion_reason = NULL "
        "WHERE completion_reason = 'resident_canceled'",
    )
    op.execute(
        "ALTER TYPE request_completion_reason RENAME TO request_completion_reason_old",
    )
    op.execute(
        "CREATE TYPE request_completion_reason AS ENUM "
        "('resident_accepted', 'resident_rejected', 'auto_closed')",
    )
    op.execute(
        "ALTER TABLE requests ALTER COLUMN completion_reason TYPE "
        "request_completion_reason "
        "USING completion_reason::text::request_completion_reason",
    )
    op.execute("DROP TYPE request_completion_reason_old")
