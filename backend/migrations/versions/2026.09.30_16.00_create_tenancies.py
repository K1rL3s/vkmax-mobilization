"""create tenancies

Revision ID: 5a1c8e3f7b24
Revises: 3f9d6b2e8a41
Create Date: 2026-09-30 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5a1c8e3f7b24"
down_revision: str | None = "3f9d6b2e8a41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenancies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("flat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_by", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["flat_id"],
            ["flats.id"],
            name="fk_tenancies_flat_id_flats",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_tenancies_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["ended_by"],
            ["users.id"],
            name="fk_tenancies_ended_by_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenancies"),
    )
    op.create_index("ix_tenancies_flat_id", "tenancies", ["flat_id"])


def downgrade() -> None:
    op.drop_index("ix_tenancies_flat_id", table_name="tenancies")
    op.drop_table("tenancies")
