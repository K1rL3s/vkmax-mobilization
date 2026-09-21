from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Table

from zheka.core.enums import OrgRole
from zheka.infra.database.tables._columns import created_at_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

org_invites_table = Table(
    "org_invites",
    metadata,
    Column("code", String(16), primary_key=True),
    created_at_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=False),
    Column("role", pg_enum(OrgRole, "org_role"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("max_activations", Integer, nullable=False),
    Column("activations_used", Integer, default=0, server_default="0", nullable=False),
    Column("created_by", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)

flat_invites_table = Table(
    "flat_invites",
    metadata,
    Column("code", String(16), primary_key=True),
    created_at_column(),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=False),
    Column("created_by", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("max_activations", Integer, nullable=False),
    Column("activations_used", Integer, default=0, server_default="0", nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)
