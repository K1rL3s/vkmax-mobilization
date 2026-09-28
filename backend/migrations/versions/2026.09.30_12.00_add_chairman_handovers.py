"""add chairman handovers

Revision ID: 3f8d2a71c5e9
Revises: 7b3e5c0a91d4
Create Date: 2026-09-30 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f8d2a71c5e9"
down_revision: str | None = "7b3e5c0a91d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE residents SET is_chairman = false WHERE is_chairman AND id NOT IN "
            "(SELECT min(id) FROM residents WHERE is_chairman GROUP BY house_id)",
        ),
    )
    op.create_index(
        "ix_residents_house_chairman",
        "residents",
        ["house_id"],
        unique=True,
        postgresql_where=sa.text("is_chairman"),
    )
    op.create_table(
        "chairman_handovers",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"]),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index(
        "ix_chairman_handovers_house_open",
        "chairman_handovers",
        ["house_id"],
        unique=True,
        postgresql_where=sa.text("decided_at IS NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chairman_handovers_house_open",
        table_name="chairman_handovers",
    )
    op.drop_table("chairman_handovers")
    op.drop_index("ix_residents_house_chairman", table_name="residents")
