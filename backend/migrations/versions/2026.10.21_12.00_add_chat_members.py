"""add chat members

Revision ID: 3d8a6f1c4b72
Revises: 7b3e5c9a1d24
Create Date: 2026-10-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3d8a6f1c4b72"
down_revision: str | None = "7b3e5c9a1d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chats", sa.Column("link", sa.String(), nullable=True))
    op.create_table(
        "chat_members",
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.chat_id"],
            name=op.f("fk_chat_members_chat_id_chats"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_members_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("chat_id", "user_id", name=op.f("pk_chat_members")),
    )


def downgrade() -> None:
    op.drop_table("chat_members")
    op.drop_column("chats", "link")
