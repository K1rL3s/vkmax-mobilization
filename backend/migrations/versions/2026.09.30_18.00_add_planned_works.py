"""add planned works and documents to announcements

Revision ID: 5b0e7c2a91f4
Revises: d20e28bc334d
Create Date: 2026-09-30 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5b0e7c2a91f4"
down_revision: str | None = "d20e28bc334d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUEST_CATEGORY = postgresql.ENUM(
    "leak",
    "elevator",
    "garbage",
    "heating",
    "water_supply",
    "electricity",
    "entrance",
    "yard",
    "meter_error",
    "charge_dispute",
    "other",
    name="request_category",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("works_category", REQUEST_CATEGORY, nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("works_from", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column("works_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "announcements",
        sa.Column(
            "documents",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("announcements", "documents")
    op.drop_column("announcements", "works_until")
    op.drop_column("announcements", "works_from")
    op.drop_column("announcements", "works_category")
