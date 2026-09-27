"""add ballot index to poll votes

Revision ID: 4c1d9e7a2b85
Revises: e2b2a95b7260
Create Date: 2026-09-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c1d9e7a2b85"
down_revision: str | None = "e2b2a95b7260"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "poll_votes",
        sa.Column("choice_index", sa.SmallInteger(), nullable=True),
    )
    op.execute(
        "UPDATE poll_votes SET choice_index = ranked.choice_index "
        "FROM (SELECT id, row_number() OVER "
        "(PARTITION BY poll_id, user_id ORDER BY id) - 1 AS choice_index "
        "FROM poll_votes) AS ranked "
        "WHERE poll_votes.id = ranked.id",
    )
    op.execute(
        "UPDATE poll_votes SET counted_by_area = false "
        "WHERE counted_by_area AND user_id <> ("
        "SELECT first.user_id FROM poll_votes AS first "
        "WHERE first.poll_id = poll_votes.poll_id "
        "AND first.flat_id = poll_votes.flat_id AND first.counted_by_area "
        "ORDER BY first.id LIMIT 1)",
    )
    op.alter_column("poll_votes", "choice_index", nullable=False)
    op.create_unique_constraint(
        "uq_poll_votes_ballot",
        "poll_votes",
        ["poll_id", "user_id", "choice_index"],
    )
    op.create_index(
        "ix_poll_votes_flat_ballot",
        "poll_votes",
        ["poll_id", "flat_id", "choice_index"],
        unique=True,
        postgresql_where=sa.text("counted_by_area"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_poll_votes_flat_ballot",
        table_name="poll_votes",
        postgresql_where=sa.text("counted_by_area"),
    )
    op.drop_constraint("uq_poll_votes_ballot", "poll_votes", type_="unique")
    op.drop_column("poll_votes", "choice_index")
