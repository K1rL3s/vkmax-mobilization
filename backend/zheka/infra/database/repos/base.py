from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseAlchemyRepo:
    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _count(self, stmt: Select[Any]) -> int:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await self._session.execute(count_stmt)
        return result.scalar_one()
