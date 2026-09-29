from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    false,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from zheka.core.enums import NoticeStatus, RequestCategory, ResidentRole
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
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
    Column("delivered_direct", Integer, nullable=True),
    Column("delivered_chat", Integer, nullable=True),
    Column("entrances", ARRAY(Integer), nullable=True),
    Column("flat_ids", ARRAY(BigInteger), nullable=True),
    Column("poll_id", BigInteger, ForeignKey("polls.id"), nullable=True),
    Column(
        "works_category",
        pg_enum(RequestCategory, "request_category"),
        nullable=True,
    ),
    Column("works_from", DateTime(timezone=True), nullable=True),
    Column("works_until", DateTime(timezone=True), nullable=True),
    Column("documents", JSONB, default=list, server_default="[]", nullable=False),
    Index(None, "house_ids", postgresql_using="gin"),
)

notice_deliveries_table = Table(
    "notice_deliveries",
    metadata,
    Column(
        "announcement_id",
        BigInteger,
        ForeignKey("announcements.id"),
        primary_key=True,
    ),
    Column("user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=True),
    Column("role", pg_enum(ResidentRole, "resident_role"), nullable=True),
    Column("verified", Boolean, nullable=False),
    Column("status", pg_enum(NoticeStatus, "notice_status"), nullable=False),
    Column("at", DateTime(timezone=True), nullable=True),
)
