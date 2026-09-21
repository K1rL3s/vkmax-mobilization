from collections.abc import Collection, Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import ChatStatus
from zheka.core.ids import HouseId, MaxChatId, UserId
from zheka.infra.database.models import Chat
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.chats import chats_table

# одно определение на карточку дома и рассылку: бот, которого удалили из чата,
# оставляет bound_at, и по одному bound_at карточка звала бы привязанным чат,
# куда никто не может написать
BOUND_CHAT = and_(
    chats_table.c.house_id.is_not(None),
    chats_table.c.bound_at.is_not(None),
    chats_table.c.status == ChatStatus.ACTIVE,
)


class ChatsRepo(BaseAlchemyRepo):
    async def list_for_houses(
        self,
        house_ids: Collection[HouseId],
    ) -> Sequence[Chat]:
        if not house_ids:
            return []
        # без прав администратора бот в чат MAX не пишет, и отправка туда
        # была бы гарантированной ошибкой на каждом объявлении
        stmt = select(Chat).where(
            chats_table.c.house_id.in_(house_ids),
            BOUND_CHAT,
            chats_table.c.bot_is_admin.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get(self, chat_id: MaxChatId) -> Chat | None:
        stmt = select(Chat).where(chats_table.c.chat_id == chat_id)
        # аннотация обязательна: Chat отображен императивно, и scalar()
        # для такой сущности возвращает Any
        chat: Chat | None = await self._session.scalar(stmt)
        return chat

    async def upsert_added(self, chat_id: MaxChatId, title: str) -> None:
        # каждое добавление - новая привязка: вернувший бота человек может
        # быть не тем, кто привязывал в прошлый раз, и унаследованная
        # привязка обошла бы проверку его прав
        fresh = {
            "title": title,
            "status": ChatStatus.ACTIVE,
            "bot_is_admin": False,
            "house_id": None,
            "bound_by": None,
            "bound_at": None,
        }
        insert = pg_insert(chats_table).values(chat_id=chat_id, **fresh)
        stmt = insert.on_conflict_do_update(
            index_elements=[chats_table.c.chat_id],
            set_=fresh,
        )
        await self._session.execute(stmt)

    async def set_removed(self, chat_id: MaxChatId) -> None:
        stmt = (
            update(chats_table)
            .where(chats_table.c.chat_id == chat_id)
            .values(status=ChatStatus.REMOVED, bot_is_admin=False)
        )
        await self._session.execute(stmt)

    async def bind(self, chat: Chat, house_id: HouseId, by: UserId) -> None:
        chat.house_id = house_id
        chat.bound_by = by
        chat.bound_at = datetime.now(UTC)
        await self._session.flush()

    async def set_admin(self, chat: Chat, is_admin: bool) -> None:
        chat.bot_is_admin = is_admin
        await self._session.flush()
