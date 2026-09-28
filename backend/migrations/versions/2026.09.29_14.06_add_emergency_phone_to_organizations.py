"""add emergency phone to organizations

Revision ID: 2c4883d34de8
Revises: 3c1d9e7a52f0
Create Date: 2026-09-29 14:06:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2c4883d34de8"
down_revision: str | None = "3c1d9e7a52f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_INNS = ("9900000001", "9900000010", "9900000020", "9900000030", "9900000040")


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("emergency_phone", sa.String(), nullable=True),
    )
    for number, inn in enumerate(DEMO_INNS, start=1):
        op.execute(
            sa.text(
                "UPDATE organizations SET emergency_phone = :phone "
                "WHERE is_demo AND inn = :inn",
            ).bindparams(phone=f"+7 (000) 000-01-{number:02d}", inn=inn),
        )


def downgrade() -> None:
    op.drop_column("organizations", "emergency_phone")
