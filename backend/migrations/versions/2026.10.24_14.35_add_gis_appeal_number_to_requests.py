"""add gis appeal number to requests

Revision ID: 5af68b5c086c
Revises: b6a69b75f348
Create Date: 2026-10-24 14:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5af68b5c086c"
down_revision: str | None = "b6a69b75f348"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("gis_appeal_number", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("requests", "gis_appeal_number")
