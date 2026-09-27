"""pad demo accounts

Revision ID: e2b2a95b7260
Revises: 89db107154e3
Create Date: 2026-09-27 19:56:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e2b2a95b7260"
down_revision: str | None = "89db107154e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE flats SET account_no = lpad(number, 10, '0') "
        "WHERE account_no LIKE 'ДЕМО-%' AND length(number) <= 10",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE flats SET account_no = 'ДЕМО-' || house_id || '-' || number "
        "WHERE account_no = lpad(number, 10, '0')",
    )
