"""add request visits

Revision ID: 9e2b7c4d5a18
Revises: 001b0bb760df
Create Date: 2026-10-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9e2b7c4d5a18"
down_revision: str | None = "001b0bb760df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "access_requests",
        sa.Column("request_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_access_requests_request_id_requests"),
        "access_requests",
        "requests",
        ["request_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_access_requests_request_id"),
        "access_requests",
        ["request_id"],
    )
    op.add_column(
        "access_requests",
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("access_slots", sa.Column("minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("access_slots", "minutes")
    op.drop_column("access_requests", "canceled_at")
    op.drop_index(op.f("ix_access_requests_request_id"), table_name="access_requests")
    op.drop_constraint(
        op.f("fk_access_requests_request_id_requests"),
        "access_requests",
        type_="foreignkey",
    )
    op.drop_column("access_requests", "request_id")
