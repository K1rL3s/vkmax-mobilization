"""add announcement entrances and flat_ids

Revision ID: 3ebdc02597be
Revises: 5e7a1c93b2d4
Create Date: 2026-09-30 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3ebdc02597be"
down_revision: str | None = "5e7a1c93b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("entrances", postgresql.ARRAY(sa.Integer()), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("flat_ids", postgresql.ARRAY(sa.BigInteger()), nullable=True),
    )
    op.execute(
        "UPDATE flats SET entrance = 1 WHERE entrance IS NULL AND number LIKE 'Д%'",
    )


def downgrade() -> None:
    op.drop_column("announcements", "flat_ids")
    op.drop_column("announcements", "entrances")
