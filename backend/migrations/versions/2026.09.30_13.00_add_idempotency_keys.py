"""add idempotency keys

Revision ID: 5a2e7d41b0c6
Revises: 3f8d2a71c5e9
Create Date: 2026-09-30 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5a2e7d41b0c6"
down_revision: str | None = "3f8d2a71c5e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "key"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
