"""add request escalated_at

Revision ID: 154d898afef3
Revises: 3c7a9e1b5d42
Create Date: 2026-09-29 15:32:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "154d898afef3"
down_revision: str | None = "3c7a9e1b5d42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("requests", "escalated_at")
