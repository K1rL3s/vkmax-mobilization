from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables.base import metadata

access_requests_table = Table(
    "access_requests",
    metadata,
    id_column(),
    created_at_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=False),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("reason", Text, nullable=False),
    Column("date", Date, nullable=False),
    Column("created_by", BigInteger, ForeignKey("users.id"), nullable=False),
)

access_slots_table = Table(
    "access_slots",
    metadata,
    id_column(),
    Column(
        "access_request_id",
        BigInteger,
        ForeignKey("access_requests.id"),
        nullable=False,
    ),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("capacity", Integer, nullable=False),
)

access_targets_table = Table(
    "access_targets",
    metadata,
    id_column(),
    Column(
        "access_request_id",
        BigInteger,
        ForeignKey("access_requests.id"),
        nullable=False,
    ),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=False),
    Column("slot_id", BigInteger, ForeignKey("access_slots.id"), nullable=True),
    Column("responded_at", DateTime(timezone=True), nullable=True),
    Column("notified_message_ids", JSONB, default=list, nullable=False),
)
