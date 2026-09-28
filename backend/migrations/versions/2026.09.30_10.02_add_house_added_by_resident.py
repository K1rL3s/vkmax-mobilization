"""add house added_by_resident

Revision ID: 8d2f4b61c7a9
Revises: 2a6c9f1d4b83
Create Date: 2026-09-30 10:02:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d2f4b61c7a9"
down_revision: str | None = "2a6c9f1d4b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "houses",
        sa.Column(
            "added_by_resident",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("houses", "added_by_resident")
