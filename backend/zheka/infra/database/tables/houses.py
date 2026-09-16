from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables.base import metadata

houses_table = Table(
    "houses",
    metadata,
    id_column(),
    created_at_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=True),
    Column("region", String, nullable=False),
    Column("city", String, nullable=False),
    Column("street", String, nullable=False),
    Column("building", String, nullable=False),
    Column("cadastral_no", String, nullable=False),
    Column("built_year", Integer, nullable=True),
    Column("floors", Integer, nullable=True),
    Column("area", Numeric(10, 2), nullable=True),
    Column("entrances", Integer, default=1, server_default="1", nullable=False),
    Column("lat", Numeric(9, 6), nullable=True),
    Column("lon", Numeric(9, 6), nullable=True),
    Column("chat_binding_code", String(8), nullable=False, unique=True),
    Column("overhaul", JSONB, default=dict, nullable=False),
    Column("documents", JSONB, default=list, nullable=False),
    Index(None, "city", "street"),
)

flats_table = Table(
    "flats",
    metadata,
    id_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("number", String(16), nullable=False),
    Column("entrance", Integer, nullable=True),
    Column("area", Numeric(10, 2), nullable=True),
    Column("account_no", String(32), nullable=True),
    UniqueConstraint("house_id", "number"),
)
