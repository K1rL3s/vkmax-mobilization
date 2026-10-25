"""add entrance to requests and request groups

Revision ID: 3c9e5d1a7b42
Revises: 12a893f0599e
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3c9e5d1a7b42"
down_revision: str | None = "12a893f0599e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("entrance", sa.Integer(), nullable=True))
    op.add_column(
        "request_groups",
        sa.Column("entrance", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("request_groups", "entrance")
    op.drop_column("requests", "entrance")
