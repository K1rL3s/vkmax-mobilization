"""fill registry org contacts

Revision ID: 3f9d6b2e8a41
Revises: 5c1e8a7d3f20
Create Date: 2026-09-30 17:00:00.000000

"""

import csv
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "3f9d6b2e8a41"
down_revision: str | None = "5c1e8a7d3f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATIONS_CSV = (
    Path(__file__).resolve().parents[2] / "zheka/seed/data/organizations.csv"
)


def upgrade() -> None:
    with ORGANIZATIONS_CSV.open(encoding="utf-8") as file:
        rows = [
            {
                "inn": row["inn"],
                "email": row["email"] or None,
                "site": row["site"] or None,
            }
            for row in csv.DictReader(file)
        ]
    op.get_bind().execute(
        sa.text(
            "UPDATE organizations SET email = :email, site = :site "
            "WHERE inn = :inn AND registered_at IS NULL",
        ),
        rows,
    )


def downgrade() -> None:
    pass
