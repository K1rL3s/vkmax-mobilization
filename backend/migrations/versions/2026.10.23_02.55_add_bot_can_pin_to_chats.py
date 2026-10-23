"""add bot can pin to chats

Revision ID: 443dc2f9d2f8
Revises: 3d8a6f1c4b72
Create Date: 2026-10-23 02:55:19.525809

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "443dc2f9d2f8"
down_revision: str | None = "3d8a6f1c4b72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "bot_can_pin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute("UPDATE chats SET bot_can_pin = bot_is_admin")


def downgrade() -> None:
    op.drop_column("chats", "bot_can_pin")
