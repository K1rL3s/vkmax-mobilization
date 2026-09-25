from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseAlchemyRepo:
    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _page[T](
        self,
        stmt: Select[tuple[T]],
        limit: int,
        offset: int,
    ) -> tuple[Sequence[T], int]:
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await self._session.execute(count_stmt)).scalar_one()
        page_stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total
