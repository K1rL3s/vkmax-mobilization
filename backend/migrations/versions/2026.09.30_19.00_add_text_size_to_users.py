"""add text size to users

Revision ID: 8c4f2a7d1e93
Revises: 5a1c8e3f7b24
Create Date: 2026-09-30 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8c4f2a7d1e93"
down_revision: str | None = "5a1c8e3f7b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "text_size",
            sa.String(8),
            server_default="normal",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "text_size")
