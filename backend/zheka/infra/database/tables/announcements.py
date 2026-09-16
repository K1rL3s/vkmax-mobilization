from sqlalchemy import ARRAY, BigInteger, Column, ForeignKey, Index, String, Table, Text

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
    Index(None, "house_ids", postgresql_using="gin"),
)
