"""add notice deliveries and announcement poll_id

Revision ID: d20e28bc334d
Revises: 3ebdc02597be
Create Date: 2026-09-30 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d20e28bc334d"
down_revision: str | None = "3ebdc02597be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("poll_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_announcements_poll_id_polls"),
        "announcements",
        "polls",
        ["poll_id"],
        ["id"],
    )
    sa.Enum(
        "pending",
        "delivered",
        "failed",
        "muted",
        "bot_stopped",
        name="notice_status",
    ).create(op.get_bind())
    op.create_table(
        "notice_deliveries",
        sa.Column("announcement_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("flat_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM("owner", "tenant", name="resident_role", create_type=False),
            nullable=True,
        ),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "delivered",
                "failed",
                "muted",
                "bot_stopped",
                name="notice_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["announcement_id"],
            ["announcements.id"],
            name=op.f("fk_notice_deliveries_announcement_id_announcements"),
        ),
        sa.ForeignKeyConstraint(
            ["flat_id"],
            ["flats.id"],
            name=op.f("fk_notice_deliveries_flat_id_flats"),
        ),
        sa.ForeignKeyConstraint(
            ["house_id"],
            ["houses.id"],
            name=op.f("fk_notice_deliveries_house_id_houses"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notice_deliveries_user_id_users"),
        ),
        sa.PrimaryKeyConstraint(
            "announcement_id",
            "user_id",
            name=op.f("pk_notice_deliveries"),
        ),
    )


def downgrade() -> None:
    op.drop_table("notice_deliveries")
    sa.Enum(name="notice_status").drop(op.get_bind())
    op.drop_constraint(
        op.f("fk_announcements_poll_id_polls"),
        "announcements",
        type_="foreignkey",
    )
    op.drop_column("announcements", "poll_id")
