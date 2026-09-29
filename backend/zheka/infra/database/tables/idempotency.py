from sqlalchemy import BigInteger, Column, ForeignKey, String, Table, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from zheka.infra.database.tables._columns import created_at_column
from zheka.infra.database.tables.base import metadata

idempotency_keys_table = Table(
    "idempotency_keys",
    metadata,
    Column("user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
    Column("key", Uuid, primary_key=True),
    Column("route", String(64), nullable=False),
    Column("response", JSONB, nullable=True),
    created_at_column(),
)
