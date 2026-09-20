from collections.abc import Collection, Sequence

from sqlalchemy import select

from zheka.core.enums import ChatStatus
from zheka.core.ids import HouseId
from zheka.infra.database.models import Chat
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.chats import chats_table


class ChatsRepo(BaseAlchemyRepo):
    async def list_for_houses(
        self,
        house_ids: Collection[HouseId],
    ) -> Sequence[Chat]:
        if not house_ids:
            return []
        stmt = select(Chat).where(
            chats_table.c.house_id.in_(house_ids),
            chats_table.c.status == ChatStatus.ACTIVE,
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
