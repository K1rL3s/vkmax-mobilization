"""add request deadlines

Revision ID: 6f4b87d066b4
Revises: 9f3a6c1e5d27
Create Date: 2026-09-29 10:04:00.000000

"""

from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

NON_WORKING_WEEKDAYS = (
    "2026-01-01",
    "2026-01-02",
    "2026-01-05",
    "2026-01-06",
    "2026-01-07",
    "2026-01-08",
    "2026-01-09",
    "2026-02-23",
    "2026-03-09",
    "2026-05-01",
    "2026-05-11",
    "2026-06-12",
    "2026-11-04",
    "2026-12-31",
    "2027-01-01",
    "2027-01-04",
    "2027-01-05",
    "2027-01-06",
    "2027-01-07",
    "2027-01-08",
    "2027-02-22",
    "2027-02-23",
    "2027-03-08",
    "2027-05-03",
    "2027-05-10",
    "2027-06-14",
    "2027-11-04",
    "2027-11-05",
    "2027-12-31",
)
WORKING_WEEKENDS = ("2027-02-20",)

revision: str = "6f4b87d066b4"
down_revision: str | None = "9f3a6c1e5d27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "requests",
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("react_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE requests SET
            deadline_at = created_at + CASE category
                WHEN 'water_supply' THEN interval '4 hours'
                WHEN 'heating' THEN interval '16 hours'
                WHEN 'elevator' THEN interval '24 hours'
                WHEN 'garbage' THEN interval '24 hours'
                WHEN 'electricity' THEN interval '24 hours'
                ELSE interval '72 hours'
            END,
            react_deadline_at = CASE category
                WHEN 'leak' THEN created_at + interval '30 minutes'
            END
        """,
    )
    op.execute(
        sa.text(
            """
            UPDATE requests AS r SET deadline_at = (
                SELECT (day + interval '1 day' - interval '1 microsecond')
                    AT TIME ZONE h.timezone
                FROM generate_series(
                    date_trunc('day', r.created_at AT TIME ZONE h.timezone)
                        + interval '1 day',
                    date_trunc('day', r.created_at AT TIME ZONE h.timezone)
                        + interval '60 days',
                    interval '1 day'
                ) AS day
                WHERE day::date = ANY(CAST(:working AS date[]))
                    OR (
                        extract(isodow FROM day) < 6
                        AND NOT day::date = ANY(CAST(:holidays AS date[]))
                    )
                ORDER BY day
                OFFSET 9
                LIMIT 1
            )
            FROM houses AS h
            WHERE h.id = r.house_id
                AND r.category IN ('meter_error', 'charge_dispute', 'other')
            """,
        ).bindparams(
            working=[date.fromisoformat(day) for day in WORKING_WEEKENDS],
            holidays=[date.fromisoformat(day) for day in NON_WORKING_WEEKDAYS],
        ),
    )
    op.alter_column("requests", "deadline_at", nullable=False)


def downgrade() -> None:
    op.drop_column("requests", "react_deadline_at")
    op.drop_column("requests", "deadline_at")
