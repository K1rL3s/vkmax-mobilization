"""add announcement delivery

Revision ID: 3c7a9e1b5d42
Revises: 6b8e2d4f1a93
Create Date: 2026-09-29 15:31:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c7a9e1b5d42"
down_revision: str | None = "6b8e2d4f1a93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("delivered_direct", sa.Integer(), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("delivered_chat", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("announcements", "delivered_chat")
    op.drop_column("announcements", "delivered_direct")
