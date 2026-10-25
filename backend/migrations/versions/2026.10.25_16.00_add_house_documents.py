"""add house documents, drop houses.documents

Revision ID: 12a893f0599e
Revises: a627c7f3b835
Create Date: 2026-10-25 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "12a893f0599e"
down_revision: str | None = "a627c7f3b835"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "house_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.Column("house_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["house_id"],
            ["houses.id"],
            name=op.f("fk_house_documents_house_id_houses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_house_documents")),
    )
    op.create_index(
        op.f("ix_house_documents_house_id"),
        "house_documents",
        ["house_id"],
    )
    op.drop_column("houses", "documents")


def downgrade() -> None:
    op.add_column(
        "houses",
        sa.Column(
            "documents",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.alter_column("houses", "documents", server_default=None)
    op.drop_index(op.f("ix_house_documents_house_id"), table_name="house_documents")
    op.drop_table("house_documents")
