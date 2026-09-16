from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.exc import DetachedInstanceError


class BaseAlchemyModel(DeclarativeBase):
    __abstract__ = True

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )

    def __repr__(self) -> str:
        return self._repr(
            **{c.name: getattr(self, c.name) for c in self.__table__.columns},
        )

    def _repr(self, **fields: Any) -> str:
        parts = []
        attached = False
        for key, field in fields.items():
            try:
                parts.append(f"{key}={field!r}")
            except DetachedInstanceError:
                parts.append(f"{key}=DetachedInstanceError")
            else:
                attached = True

        if attached:
            return f"<{type(self).__name__}({', '.join(parts)})>"
        return f"<{type(self).__name__} {id(self)}>"
