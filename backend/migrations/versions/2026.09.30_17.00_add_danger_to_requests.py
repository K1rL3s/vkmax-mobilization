"""add danger to requests

Revision ID: 5e7a1c93b2d4
Revises: c2898f019ff9
Create Date: 2026-09-30 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5e7a1c93b2d4"
down_revision: str | None = "c2898f019ff9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("requests", sa.Column("danger", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("requests", "danger")
