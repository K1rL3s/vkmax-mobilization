"""index foreign keys covered only by partial indexes

Revision ID: b6a69b75f348
Revises: fba27f8b4756
Create Date: 2026-10-24 14:20:31.099560

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b6a69b75f348"
down_revision: str | None = "fba27f8b4756"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_chairman_handovers_house_id"),
        "chairman_handovers",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        "ix_flat_verification_requests_by_user",
        "flat_verification_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_residents_house_id"),
        "residents",
        ["house_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_residents_house_id"), table_name="residents")
    op.drop_index(
        "ix_flat_verification_requests_by_user",
        table_name="flat_verification_requests",
    )
    op.drop_index(
        op.f("ix_chairman_handovers_house_id"),
        table_name="chairman_handovers",
    )
