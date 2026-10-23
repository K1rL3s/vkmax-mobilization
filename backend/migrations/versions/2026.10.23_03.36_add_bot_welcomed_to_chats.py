"""add bot_welcomed to chats

Revision ID: 001b0bb760df
Revises: 443dc2f9d2f8
Create Date: 2026-10-23 03:36:13.374073

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001b0bb760df"
down_revision: str | None = "443dc2f9d2f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "bot_welcomed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        """
        UPDATE chats SET bot_welcomed = true
        WHERE bound_at IS NOT NULL AND (
            bot_is_admin OR EXISTS (
                SELECT 1 FROM events
                WHERE events.type = 'chat_admin_granted'
                  AND events.payload @> jsonb_build_object('chat_id', chats.chat_id)
                  AND events.created_at >= chats.bound_at
            )
        )
        """,
    )


def downgrade() -> None:
    op.drop_column("chats", "bot_welcomed")
