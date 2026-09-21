from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Table, Time

from zheka.core.enums import AppointmentStatus
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

reception_windows_table = Table(
    "reception_windows",
    metadata,
    id_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=False),
    Column("weekday", Integer, nullable=False),
    Column("time_from", Time, nullable=False),
    Column("time_to", Time, nullable=False),
    Column("slot_minutes", Integer, nullable=False),
    Column("capacity", Integer, nullable=False, server_default="1"),
)

appointments_table = Table(
    "appointments",
    metadata,
    id_column(),
    created_at_column(),
    Column("org_id", BigInteger, ForeignKey("organizations.id"), nullable=False),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("request_id", BigInteger, ForeignKey("requests.id"), nullable=True),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("status", pg_enum(AppointmentStatus, "appointment_status"), nullable=False),
    Column("reminder_sent_at", DateTime(timezone=True), nullable=True),
)
