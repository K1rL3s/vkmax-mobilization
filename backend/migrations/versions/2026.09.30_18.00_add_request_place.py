"""add request place

Revision ID: 7b3e5c9a1d24
Revises: 8c4f2a7d1e93
Create Date: 2026-09-30 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7b3e5c9a1d24"
down_revision: str | None = "8c4f2a7d1e93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLACE = postgresql.ENUM("flat", "house", name="request_place")


def upgrade() -> None:
    PLACE.create(op.get_bind())
    op.add_column(
        "requests",
        sa.Column(
            "place",
            postgresql.ENUM(name="request_place", create_type=False),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE requests SET place = CASE
            WHEN category IN ('elevator', 'garbage', 'entrance', 'yard')
            OR regexp_replace(description, '^Повторно: ', '') IN (
                'Шумит стояк отопления',
                'Не горит свет на лестничной площадке',
                'Искрит розетка в щитке на этаже',
                'Не работает домофон'
            )
            THEN 'house'::request_place
            ELSE 'flat'::request_place
        END
        """,
    )
    op.alter_column("requests", "place", nullable=False)


def downgrade() -> None:
    op.drop_column("requests", "place")
    PLACE.drop(op.get_bind())
