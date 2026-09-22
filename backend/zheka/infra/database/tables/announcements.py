from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    false,
)
from sqlalchemy.dialects.postgresql import ARRAY

from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables.base import metadata

announcements_table = Table(
    "announcements",
    metadata,
    id_column(),
    created_at_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=False),
    Column("house_ids", ARRAY(BigInteger), nullable=False),
    Column("text", Text, nullable=False),
    Column("channels", ARRAY(String), nullable=False),
    Column("created_by", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("recipients_count", Integer, nullable=False, default=0, server_default="0"),
    Column("urgent", Boolean, nullable=False, default=False, server_default=false()),
    Index(None, "house_ids", postgresql_using="gin"),
)
