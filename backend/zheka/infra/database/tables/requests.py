from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    false,
)

from zheka.core.enums import (
    RequestCategory,
    RequestChannel,
    RequestCompletionReason,
    RequestGroupStatus,
    RequestPhotoKind,
    RequestStatus,
)
from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables._enum import pg_enum
from zheka.infra.database.tables.base import metadata

requests_table = Table(
    "requests",
    metadata,
    id_column(),
    created_at_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("flat_id", BigInteger, ForeignKey("flats.id"), nullable=True),
    Column("author_user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("category", pg_enum(RequestCategory, "request_category"), nullable=False),
    Column("description", Text, nullable=False),
    Column("status", pg_enum(RequestStatus, "request_status"), nullable=False),
    Column(
        "completion_reason",
        pg_enum(RequestCompletionReason, "request_completion_reason"),
        nullable=True,
    ),
    Column("parent_request_id", BigInteger, ForeignKey("requests.id"), nullable=True),
    Column("group_id", BigInteger, ForeignKey("request_groups.id"), nullable=True),
    Column("channel", pg_enum(RequestChannel, "request_channel"), nullable=False),
    Column("caller_name", String, nullable=True),
    Column("caller_phone", String, nullable=True),
    Column("executor_user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("rating", Integer, nullable=True),
    Column("feedback", Text, nullable=True),
    Column("accepted_at", DateTime(timezone=True), nullable=True),
    Column("done_at", DateTime(timezone=True), nullable=True),
    Column("reviewed_at", DateTime(timezone=True), nullable=True),
    Column(
        "is_staff_author",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
    Column("deadline_at", DateTime(timezone=True), nullable=False),
    Column("react_deadline_at", DateTime(timezone=True), nullable=True),
    Column("deadline_warned_at", DateTime(timezone=True), nullable=True),
    Column("overdue_notified_at", DateTime(timezone=True), nullable=True),
    Index(None, "house_id", "status"),
    Index(None, "group_id"),
    Index(None, "executor_user_id", "status"),
)

request_groups_table = Table(
    "request_groups",
    metadata,
    id_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=False),
    Column("category", pg_enum(RequestCategory, "request_category"), nullable=False),
    Column("window_started_at", DateTime(timezone=True), nullable=False),
    Column(
        "status",
        pg_enum(RequestGroupStatus, "request_group_status"),
        nullable=False,
    ),
)

request_photos_table = Table(
    "request_photos",
    metadata,
    id_column(),
    created_at_column(),
    Column("request_id", BigInteger, ForeignKey("requests.id"), nullable=False),
    Column("path", String(64), nullable=False),
    Column("kind", pg_enum(RequestPhotoKind, "request_photo_kind"), nullable=False),
    Column("uploaded_by", BigInteger, ForeignKey("users.id"), nullable=False),
)

request_status_log_table = Table(
    "request_status_log",
    metadata,
    id_column(),
    Column("request_id", BigInteger, ForeignKey("requests.id"), nullable=False),
    Column("from_status", pg_enum(RequestStatus, "request_status"), nullable=True),
    Column("to_status", pg_enum(RequestStatus, "request_status"), nullable=False),
    Column("by_user_id", BigInteger, ForeignKey("users.id"), nullable=True),
    Column("by_role", String(16), nullable=False),
    Column("at", DateTime(timezone=True), nullable=False),
)

request_messages_table = Table(
    "request_messages",
    metadata,
    id_column(),
    created_at_column(),
    Column("request_id", BigInteger, ForeignKey("requests.id"), nullable=False),
    Column("author_user_id", BigInteger, ForeignKey("users.id"), nullable=False),
    Column("author_role", String(16), nullable=False),
    Column("text", Text, nullable=False),
    Column(
        "is_internal",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
)
