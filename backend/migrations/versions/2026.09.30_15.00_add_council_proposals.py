"""add council proposals

Revision ID: 4e7a91c3b528
Revises: 9c4b1f60d7a2
Create Date: 2026-09-30 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4e7a91c3b528"
down_revision: str | None = "9c4b1f60d7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "council_proposals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("new", "accepted", "declined", name="proposal_status"),
            nullable=False,
        ),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("poll_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"]),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_council_proposals_house_id",
        "council_proposals",
        ["house_id", "created_at"],
    )
    op.create_index(
        "ix_council_proposals_author_user_id",
        "council_proposals",
        ["author_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_council_proposals_author_user_id", table_name="council_proposals")
    op.drop_index("ix_council_proposals_house_id", table_name="council_proposals")
    op.drop_table("council_proposals")
    op.execute("DROP TYPE proposal_status")
