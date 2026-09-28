"""add chat cards

Revision ID: 8d1f4b7c2e60
Revises: 154d898afef3
Create Date: 2026-09-30 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d1f4b7c2e60"
down_revision: str | None = "154d898afef3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_cards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("ref_id", sa.BigInteger(), nullable=False),
        sa.Column("mid", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.chat_id"],
            name=op.f("fk_chat_cards_chat_id_chats"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_cards")),
        sa.UniqueConstraint(
            "chat_id",
            "kind",
            "ref_id",
            name=op.f("uq_chat_cards_chat_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("chat_cards")
