from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    desc,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB

from zheka.core.enums import ServiceType
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

tariffs_table = Table(
    "tariffs",
    metadata,
    id_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("service", pg_enum(ServiceType, "service_type"), nullable=False),
    Column("value", BigInteger, nullable=False),
    Column("unit", String(16), nullable=False),
    Column("valid_from", Date, nullable=False),
    Column("document_url", String, nullable=True),
    Index(None, "house_id", "service", desc("valid_from")),
)

charges_table = Table(
    "charges",
    metadata,
    id_column(),
    created_at_column(),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=False),
    Column("period", Date, nullable=False),
    Column("lines", JSONB, nullable=False),
    Column("total", BigInteger, nullable=False),
    Column("is_closed", Boolean, default=True, server_default=true(), nullable=False),
    Column("paid_at", DateTime(timezone=True), nullable=True),
    UniqueConstraint("flat_id", "period"),
)
