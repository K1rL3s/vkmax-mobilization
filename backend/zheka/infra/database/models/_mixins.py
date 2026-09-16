from datetime import datetime

from sqlalchemy import BigInteger, ColumnElement, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def fresh_timestamp() -> ColumnElement[datetime]:
    return func.timezone("UTC", func.now())


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=fresh_timestamp(),
        server_default=fresh_timestamp(),
        nullable=False,
    )


class UpdatedAtMixin:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=fresh_timestamp(),
        onupdate=fresh_timestamp(),
        server_default=fresh_timestamp(),
        server_onupdate=fresh_timestamp(),
        nullable=False,
    )
