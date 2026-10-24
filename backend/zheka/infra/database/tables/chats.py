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
)

from zheka.infra.database.tables._columns import created_at_column, id_column
from zheka.infra.database.tables.base import metadata

chats_table = Table(
    "chats",
    metadata,
    Column("chat_id", BigInteger, primary_key=True),
    created_at_column(),
    Column("house_id", BigInteger, ForeignKey("houses.id"), nullable=True, index=True),
    Column("title", String, nullable=True),
    Column("bound_by", BigInteger, ForeignKey("users.id"), nullable=True, index=True),
    Column(
        "bot_is_admin",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
    Column(
        "bot_can_pin",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
    Column(
        "bot_welcomed",
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    ),
    Column("bound_at", DateTime(timezone=True), nullable=True),
    Column("status", String(16), nullable=False),
    Column("pins_mid", String, nullable=True),
    Column("link", String, nullable=True),
)

chat_members_table = Table(
    "chat_members",
    metadata,
    Column(
        "chat_id",
        BigInteger,
        ForeignKey("chats.chat_id"),
        primary_key=True,
    ),
    Column("user_id", BigInteger, ForeignKey("users.id"), primary_key=True, index=True),
    created_at_column(),
)

chat_pins_table = Table(
    "chat_pins",
    metadata,
    id_column(),
    created_at_column(),
    Column(
        "chat_id",
        BigInteger,
        ForeignKey("chats.chat_id"),
        nullable=False,
        index=True,
    ),
    Column("mid", String, nullable=False),
    Column("seq", BigInteger, nullable=False),
    Column("text", String, nullable=True),
    Column("pinned_by", BigInteger, ForeignKey("users.id"), nullable=False, index=True),
    Column("unpinned_at", DateTime(timezone=True), nullable=True),
    Index(
        None,
        "chat_id",
        "mid",
        unique=True,
        postgresql_where=text("unpinned_at IS NULL"),
    ),
)

chat_cards_table = Table(
    "chat_cards",
    metadata,
    id_column(),
    created_at_column(),
    Column("chat_id", BigInteger, ForeignKey("chats.chat_id"), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("ref_id", BigInteger, nullable=False),
    Column("mid", String, nullable=False),
    UniqueConstraint("chat_id", "kind", "ref_id"),
)
