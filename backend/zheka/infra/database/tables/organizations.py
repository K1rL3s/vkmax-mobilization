from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    false,
)

from zheka.core.enums import OrgRole
from zheka.infra.database.tables._columns import (
    created_at_column,
    id_column,
    updated_at_column,
)
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

organizations_table = Table(
    "organizations",
    metadata,
    id_column(),
    created_at_column(),
    Column("name", String, nullable=False),
    Column("inn", String, nullable=False, unique=True),
    Column("license_no", String, nullable=True),
    Column("phone", String, nullable=False),
    Column("address", String, nullable=False),
    Column("reception_note", String, nullable=True),
    Column("registered_at", DateTime(timezone=True), nullable=True),
    Column("is_demo", Boolean, default=False, server_default=false(), nullable=False),
)

org_settings_table = Table(
    "org_settings",
    metadata,
    Column("org_id", BigInteger, ForeignKey("organizations.id"), primary_key=True),
    updated_at_column(),
    Column(
        "meter_window_day_from",
        Integer,
        default=15,
        server_default="15",
        nullable=False,
    ),
    Column(
        "meter_window_day_to",
        Integer,
        default=25,
        server_default="25",
        nullable=False,
    ),
    Column(
        "meter_window_always_open",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
    Column("group_threshold", Integer, default=3, server_default="3", nullable=False),
    Column(
        "group_window_hours",
        Integer,
        default=24,
        server_default="24",
        nullable=False,
    ),
)

org_members_table = Table(
    "org_members",
    metadata,
    id_column(),
    created_at_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("role", pg_enum(OrgRole, "org_role"), nullable=False),
    UniqueConstraint("org_id", "user_id"),
)
