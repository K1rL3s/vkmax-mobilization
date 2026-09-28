"""add org email and site

Revision ID: 7b3e5c0a91d4
Revises: 2a6c9f1d4b83
Create Date: 2026-09-30 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7b3e5c0a91d4"
down_revision: str | None = "2a6c9f1d4b83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_INNS = ("9900000001", "9900000010", "9900000020", "9900000030", "9900000040")


def upgrade() -> None:
    op.add_column("organizations", sa.Column("email", sa.String(), nullable=True))
    op.add_column("organizations", sa.Column("site", sa.String(), nullable=True))
    for number, inn in enumerate(DEMO_INNS, start=1):
        op.execute(
            sa.text(
                "UPDATE organizations SET email = :email, site = :site "
                "WHERE is_demo AND inn = :inn",
            ).bindparams(
                email=f"priem-{number}@demo-uk.example.com",
                site=f"https://demo-uk-{number}.example.com",
                inn=inn,
            ),
        )


def downgrade() -> None:
    op.drop_column("organizations", "site")
    op.drop_column("organizations", "email")
