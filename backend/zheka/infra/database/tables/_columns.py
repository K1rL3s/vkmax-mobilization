from datetime import datetime

from sqlalchemy import BigInteger, Column, ColumnElement, DateTime, func


def fresh_timestamp() -> ColumnElement[datetime]:
    return func.timezone("UTC", func.now())


def id_column() -> Column[int]:
    return Column("id", BigInteger, primary_key=True, autoincrement=True)


def created_at_column() -> Column[datetime]:
    return Column(
        "created_at",
        DateTime(timezone=True),
        default=fresh_timestamp(),
        server_default=fresh_timestamp(),
        nullable=False,
    )


def updated_at_column() -> Column[datetime]:
    return Column(
        "updated_at",
        DateTime(timezone=True),
        default=fresh_timestamp(),
        onupdate=fresh_timestamp(),
        server_default=fresh_timestamp(),
        server_onupdate=fresh_timestamp(),
        nullable=False,
    )
