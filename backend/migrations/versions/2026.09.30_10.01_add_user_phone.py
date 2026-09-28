"""add user phone

Revision ID: 2a6c9f1d4b83
Revises: 8d1f4b7c2e60
Create Date: 2026-09-30 10:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2a6c9f1d4b83"
down_revision: str | None = "8d1f4b7c2e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=16), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone")
