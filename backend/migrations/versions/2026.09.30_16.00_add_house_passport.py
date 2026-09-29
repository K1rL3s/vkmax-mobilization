"""add house passport

Revision ID: 5c1e8a7d3f20
Revises: 5b0e7c2a91f4
Create Date: 2026-09-30 16:00:00.000000

"""

import csv
import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5c1e8a7d3f20"
down_revision: str | None = "5b0e7c2a91f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOUSES_CSV = Path(__file__).resolve().parents[2] / "zheka/seed/data/houses.csv"


def upgrade() -> None:
    op.add_column(
        "houses",
        sa.Column(
            "passport",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    with HOUSES_CSV.open(encoding="utf-8") as file:
        rows = [
            {
                "city": row["city"],
                "street": row["street"],
                "building": row["building"],
                "cadastral_no": row["cadastral_no"] or None,
                "passport": json.dumps(passport(row)),
            }
            for row in csv.DictReader(file)
        ]
    op.get_bind().execute(
        sa.text(
            "UPDATE houses SET cadastral_no = :cadastral_no, "
            "passport = CAST(:passport AS jsonb) "
            "WHERE city = :city AND street = :street AND building = :building "
            "AND NOT added_by_resident",
        ),
        rows,
    )


def downgrade() -> None:
    op.drop_column("houses", "passport")


def passport(row: dict[str, str]) -> dict[str, object]:
    return {
        "reforma_on": row["reforma_on"],
        "entrances_estimated": row["entrances_estimated"] == "1",
        "energy_class": row["energy_class"] or None,
        "wear": int(row["wear"]) if row["wear"] else None,
        "wear_on": row["wear_on"] or None,
        "condition": row["condition"] or None,
        "gis_on": row["gis_on"] or None,
    }
