"""add verification revocations

Revision ID: 9f3a6c1e5d27
Revises: 4c1d9e7a2b85
Create Date: 2026-09-28 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f3a6c1e5d27"
down_revision: str | None = "4c1d9e7a2b85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_revocations",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("flat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flat_id"],
            ["flats.id"],
            name=op.f("fk_verification_revocations_flat_id_flats"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_verification_revocations_user_id_users"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "flat_id",
            name=op.f("pk_verification_revocations"),
        ),
    )


def downgrade() -> None:
    op.drop_table("verification_revocations")
