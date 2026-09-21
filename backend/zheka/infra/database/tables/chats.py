from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    false,
)

from zheka.infra.database.tables._columns import created_at_column
from zheka.infra.database.tables.base import metadata

chats_table = Table(
    "chats",
    metadata,
    Column("chat_id", BigInteger, primary_key=True),
    created_at_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=True),
    Column("title", String, nullable=True),
    Column("bound_by", BigInteger, ForeignKey("users.id"), nullable=True),
    Column(
        "bot_is_admin", Boolean, default=False, server_default=false(), nullable=False
    ),
    Column("bound_at", DateTime(timezone=True), nullable=True),
    Column("status", String(16), nullable=False),
)
