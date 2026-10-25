"""name the chat pins chat_id index

Revision ID: bc21d9960e8b
Revises: 3c9e5d1a7b42
Create Date: 2026-10-25 20:41:04.330554

"""

from collections.abc import Sequence

from alembic import op

revision: str = "bc21d9960e8b"
down_revision: str | None = "3c9e5d1a7b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_chat_pins_by_chat", "chat_pins", ["chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_pins_by_chat", table_name="chat_pins")
