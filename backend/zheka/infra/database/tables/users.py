from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)

from zheka.core.enums import NotificationCategory, NotificationLevel
from zheka.infra.database.tables._columns import (
    created_at_column,
    id_column,
    updated_at_column,
)
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

users_table = Table(
    "users",
    metadata,
    id_column(),
    created_at_column(),
    updated_at_column(),
    Column("max_user_id", BigInteger, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("username", String, nullable=True),
    Column("consent_version", String, nullable=True),
    Column("consent_at", DateTime(timezone=True), nullable=True),
    Column("bot_stopped_at", DateTime(timezone=True), nullable=True),
    Column("max_chat_id", BigInteger, nullable=True),
    Column("phone", String(16), nullable=True),
    Column("phone_verified_at", DateTime(timezone=True), nullable=True),
)

notification_settings_table = Table(
    "notification_settings",
    metadata,
    id_column(),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column(
        "category",
        pg_enum(NotificationCategory, "notification_category"),
        nullable=False,
    ),
    Column("level", pg_enum(NotificationLevel, "notification_level"), nullable=False),
    UniqueConstraint("user_id", "category"),
)
