from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    desc,
)
from sqlalchemy.dialects.postgresql import JSONB

from zheka.core.enums import MeterType
from zheka.infra.database.tables._columns import id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

meters_table = Table(
    "meters",
    metadata,
    id_column(),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=False),
    Column("type", pg_enum(MeterType, "meter_type"), nullable=False),
    Column("tariff_zones", Integer, default=1, server_default="1", nullable=False),
    Column("serial", String(32), nullable=False),
    Column("next_verification_date", Date, nullable=True),
    # отметку никто не сбрасывает: новая дата поверки обнуляет обе стадии сама
    Column("verification_warned_at", Date, nullable=True),
    UniqueConstraint("flat_id", "type"),
)

readings_table = Table(
    "readings",
    metadata,
    id_column(),
    Column("meter_id", BigInteger, ForeignKey("meters.id"), nullable=False),
    Column("period", Date, nullable=False),
    Column("values", JSONB, nullable=False),
    Column("photo_paths", JSONB, default=list, nullable=False),
    Column("ocr_used", Boolean, nullable=False),
    Column("ocr_accepted", Boolean, nullable=False),
    Column("is_below_previous", Boolean, nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=False),
    Column("submitted_by", BigInteger, ForeignKey("users.id"), nullable=False),
    Index(None, "meter_id", "period", desc("submitted_at")),
)
