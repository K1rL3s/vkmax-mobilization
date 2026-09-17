from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
)

from zheka.core.enums import PollStatus
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

polls_table = Table(
    "polls",
    metadata,
    id_column(),
    created_at_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=True),
    Column("created_by_user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("created_by_role", String(16), nullable=False),
    Column("title", String, nullable=False),
    Column("description", Text, nullable=True),
    Column(
        "is_multiple", Boolean, default=False, server_default=false(), nullable=False
    ),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("status", pg_enum(PollStatus, "poll_status"), nullable=False),
)

poll_options_table = Table(
    "poll_options",
    metadata,
    id_column(),
    Column("poll_id", BigInteger, ForeignKey("polls.id"), nullable=False),
    Column("text", String, nullable=False),
    Column("position", Integer, nullable=False),
)

poll_votes_table = Table(
    "poll_votes",
    metadata,
    id_column(),
    created_at_column(),
    Column("poll_id", BigInteger, ForeignKey("polls.id"), nullable=False),
    Column("option_id", BigInteger, ForeignKey("poll_options.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    # житель может отвязаться от дома, а голос остается: он считается по
    # user_id и flat_id, и история собрания не переписывается задним числом
    Column(
        "resident_id",
        BigInteger,
        ForeignKey("residents.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=True),
    Column("counted_by_area", Boolean, nullable=False),
    UniqueConstraint("poll_id", "user_id"),
)
