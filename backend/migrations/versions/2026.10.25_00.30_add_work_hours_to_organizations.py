"""add work hours to organizations

Revision ID: a627c7f3b835
Revises: 5af68b5c086c
Create Date: 2026-10-25 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a627c7f3b835"
down_revision: str | None = "5af68b5c086c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("work_hours", sa.String(), nullable=True),
    )
    op.execute(
        """
        UPDATE organizations
        SET work_hours = 'пн-пт 9:00-19:00, обед 13:00-14:00'
        WHERE is_demo AND work_hours IS NULL
        """,
    )
    op.execute(
        """
        UPDATE organizations
        SET address = first_house.city || ', ' || first_house.street || ', '
            || first_house.building || ', офис 1'
        FROM (
            SELECT DISTINCT ON (org_id) org_id, city, street, building
            FROM houses
            WHERE org_id IS NOT NULL
            ORDER BY org_id, id
        ) AS first_house
        WHERE first_house.org_id = organizations.id
            AND organizations.is_demo
            AND organizations.address = 'Адрес вымышлен, организация создана для демо'
        """,
    )


def downgrade() -> None:
    op.drop_column("organizations", "work_hours")
