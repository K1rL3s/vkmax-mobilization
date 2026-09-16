from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Table
from sqlalchemy.dialects.postgresql import JSONB

from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables.base import metadata

events_table = Table(
    "events",
    metadata,
    id_column(),
    created_at_column(),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("type", String(48), nullable=False),
    Column("payload", JSONB, nullable=False),
    Index(None, "type", "created_at"),
)
