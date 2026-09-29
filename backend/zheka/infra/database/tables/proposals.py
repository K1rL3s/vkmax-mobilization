from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Table, Text

from zheka.core.enums import ProposalStatus
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

council_proposals_table = Table(
    "council_proposals",
    metadata,
    id_column(),
    created_at_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("author_user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("text", Text, nullable=False),
    Column("status", pg_enum(ProposalStatus, "proposal_status"), nullable=False),
    Column("answer", Text, nullable=True),
    Column("answered_at", DateTime(timezone=True), nullable=True),
    Column("poll_id", BigInteger, ForeignKey("polls.id"), nullable=True),
    Index(None, "house_id", "created_at"),
    Index(None, "author_user_id", "created_at"),
)
