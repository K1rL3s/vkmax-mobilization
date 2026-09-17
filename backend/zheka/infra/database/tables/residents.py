from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    UniqueConstraint,
    false,
    text,
    true,
)

from zheka.core.enums import ResidentRole, ResidentStatus, VerificationStatus
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

residents_table = Table(
    "residents",
    metadata,
    id_column(),
    created_at_column(),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=True),
    Column("role", pg_enum(ResidentRole, "resident_role"), nullable=False),
    Column(
        "can_see_charges",
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    ),
    Column("can_vote", Boolean, default=True, server_default=true(), nullable=False),
    Column("verified_at", DateTime(timezone=True), nullable=True),
    Column("verified_by", BigInteger, ForeignKey("users.id"), nullable=True),
    Column(
        "status",
        pg_enum(ResidentStatus, "resident_status"),
        default=ResidentStatus.ACTIVE,
        server_default=ResidentStatus.ACTIVE.value,
        nullable=False,
    ),
    Column("block_reason", String, nullable=True),
    Column(
        "is_chairman",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
    UniqueConstraint("user_id", "house_id"),
)

flat_verification_requests_table = Table(
    "flat_verification_requests",
    metadata,
    id_column(),
    created_at_column(),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("account_no", String, nullable=False),
    Column("comment", String, nullable=True),
    Column(
        "status",
        pg_enum(VerificationStatus, "verification_status"),
        nullable=False,
    ),
    Column("decided_by", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("decided_at", DateTime(timezone=True), nullable=True),
    Column("reason", String, nullable=True),
    # вторую заявку в ожидании по той же квартире держит база, а не чтение
    # перед записью: два параллельных запроса прошли бы его оба
    Index(
        None,
        "user_id",
        "flat_id",
        unique=True,
        postgresql_where=text("status = 'pending'"),
    ),
)

demand_signals_table = Table(
    "demand_signals",
    metadata,
    id_column(),
    created_at_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    UniqueConstraint("house_id", "user_id"),
)
