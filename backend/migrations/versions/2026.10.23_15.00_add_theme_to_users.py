"""add theme to users

Revision ID: 4c7e1a9b3d62
Revises: 9e2b7c4d5a18
Create Date: 2026-10-23 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c7e1a9b3d62"
down_revision: str | None = "9e2b7c4d5a18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "theme",
            sa.String(8),
            server_default="system",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "theme")
