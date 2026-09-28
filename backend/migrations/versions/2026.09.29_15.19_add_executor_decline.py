"""add executor decline

Revision ID: 6b8e2d4f1a93
Revises: 2c4883d34de8
Create Date: 2026-09-29 15:19:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6b8e2d4f1a93"
down_revision: str | None = "2c4883d34de8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "request_messages",
        sa.Column(
            "is_internal",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_table(
        "org_category_executors",
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(name="request_category", create_type=False),
            nullable=False,
        ),
        sa.Column("executor_user_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["executor_user_id"],
            ["users.id"],
            name=op.f("fk_org_category_executors_executor_user_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_org_category_executors_org_id_organizations"),
        ),
        sa.PrimaryKeyConstraint(
            "org_id",
            "category",
            name=op.f("pk_org_category_executors"),
        ),
    )


def downgrade() -> None:
    op.drop_table("org_category_executors")
    op.drop_column("request_messages", "is_internal")
