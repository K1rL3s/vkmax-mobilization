from collections.abc import Collection, Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, delete, exists, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import ChatCardKind, ChatStatus
from zheka.core.ids import HouseId, MaxChatId, UserId
from zheka.core.models import BotRights
from zheka.infra.database.models import Chat, ChatCard, ChatPin
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.chats import (
    chat_cards_table,
    chat_members_table,
    chat_pins_table,
    chats_table,
)
from zheka.infra.database.tables.polls import polls_table
from zheka.infra.database.tables.requests import request_groups_table, requests_table

BOUND_CHAT = and_(
    chats_table.c.house_id.is_not(None),
    chats_table.c.bound_at.is_not(None),
    chats_table.c.status == ChatStatus.ACTIVE,
)
CARD_SOURCES = {
    ChatCardKind.REQUEST: requests_table,
    ChatCardKind.GROUP: request_groups_table,
    ChatCardKind.POLL: polls_table,
}


class ChatsRepo(BaseAlchemyRepo):
    async def list_for_houses(self, house_ids: Collection[HouseId]) -> Sequence[Chat]:
        stmt = select(Chat).where(
            chats_table.c.house_id.in_(house_ids),
            BOUND_CHAT,
            chats_table.c.bot_is_admin.is_(True),
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get(self, chat_id: MaxChatId) -> Chat | None:
        stmt = select(Chat).where(chats_table.c.chat_id == chat_id)
        chat: Chat | None = await self._session.scalar(stmt)
        return chat

    async def upsert_added(
        self,
        chat_id: MaxChatId,
        title: str,
        link: str | None,
    ) -> None:
        fresh = {
            "title": title,
            "link": link,
            "status": ChatStatus.ACTIVE,
            "bot_is_admin": False,
            "bot_can_pin": False,
            "bot_welcomed": False,
            "house_id": None,
            "bound_by": None,
            "bound_at": None,
            "pins_mid": None,
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
            .values(status=ChatStatus.REMOVED, bot_is_admin=False, bot_can_pin=False)
        )
        await self._session.execute(stmt)

    async def bind(self, chat: Chat, house_id: HouseId, by: UserId) -> None:
        chat.house_id = house_id
        chat.bound_by = by
        chat.bound_at = datetime.now(UTC)
        await self._session.flush()

    async def set_admin(self, chat: Chat, rights: BotRights) -> None:
        chat.bot_is_admin = rights.is_admin
        chat.bot_can_pin = rights.is_admin and rights.can_pin
        await self._session.flush()

    async def joinable(self, house_id: HouseId) -> Chat | None:
        stmt = (
            select(Chat)
            .where(
                chats_table.c.house_id == house_id,
                BOUND_CHAT,
                chats_table.c.bot_is_admin.is_(True),
            )
            .order_by(chats_table.c.bound_at.desc(), chats_table.c.chat_id)
            .limit(1)
        )
        chat: Chat | None = await self._session.scalar(stmt)
        return chat

    async def is_member(self, chat_id: MaxChatId, user_id: UserId) -> bool:
        stmt = select(
            exists().where(
                chat_members_table.c.chat_id == chat_id,
                chat_members_table.c.user_id == user_id,
            ),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def add_member(self, chat_id: MaxChatId, user_id: UserId) -> None:
        stmt = (
            pg_insert(chat_members_table)
            .values(chat_id=chat_id, user_id=user_id)
            .on_conflict_do_nothing()
        )
        await self._session.execute(stmt)

    async def remove_member(self, chat_id: MaxChatId, user_id: UserId) -> None:
        stmt = delete(chat_members_table).where(
            chat_members_table.c.chat_id == chat_id,
            chat_members_table.c.user_id == user_id,
        )
        await self._session.execute(stmt)

    async def drop_members(self, chat_id: MaxChatId) -> None:
        stmt = delete(chat_members_table).where(
            chat_members_table.c.chat_id == chat_id,
        )
        await self._session.execute(stmt)

    async def lock(self, chat_id: MaxChatId) -> Chat | None:
        stmt = (
            select(Chat)
            .where(chats_table.c.chat_id == chat_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        chat: Chat | None = await self._session.scalar(stmt)
        return chat

    async def list_pins(self, chat_id: MaxChatId) -> Sequence[ChatPin]:
        stmt = (
            select(ChatPin)
            .where(
                chat_pins_table.c.chat_id == chat_id,
                chat_pins_table.c.unpinned_at.is_(None),
            )
            .order_by(chat_pins_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def add_pin(self, pin: ChatPin) -> None:
        self._session.add(pin)
        await self._session.flush()

    async def set_pin_text(self, pin: ChatPin, text: str | None) -> None:
        pin.text = text
        await self._session.flush()

    async def unpin(self, pins: Collection[ChatPin], at: datetime) -> None:
        for pin in pins:
            pin.unpinned_at = at
        await self._session.flush()

    async def set_pins_mid(self, chat: Chat, mid: str | None) -> None:
        chat.pins_mid = mid
        await self._session.flush()

    async def get_card(
        self,
        chat_id: MaxChatId,
        kind: ChatCardKind,
        ref_id: int,
    ) -> ChatCard | None:
        stmt = select(ChatCard).where(
            chat_cards_table.c.chat_id == chat_id,
            chat_cards_table.c.kind == kind,
            chat_cards_table.c.ref_id == ref_id,
        )
        card: ChatCard | None = await self._session.scalar(stmt)
        return card

    async def add_card(self, card: ChatCard) -> None:
        self._session.add(card)
        await self._session.flush()

    async def drop_cards(self, chat_id: MaxChatId, mid: str | None = None) -> None:
        stmt = delete(chat_cards_table).where(chat_cards_table.c.chat_id == chat_id)
        if mid is not None:
            stmt = stmt.where(chat_cards_table.c.mid == mid)
        await self._session.execute(stmt)

    async def lock_for_card(self, kind: ChatCardKind, ref_id: int) -> Sequence[Chat]:
        source = CARD_SOURCES[kind]
        house_id = select(source.c.house_id).where(source.c.id == ref_id)
        stmt = (
            select(Chat)
            .where(
                chats_table.c.house_id == house_id.scalar_subquery(),
                BOUND_CHAT,
                chats_table.c.bot_is_admin.is_(True),
            )
            .order_by(chats_table.c.chat_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def set_welcomed(self, chat: Chat) -> None:
        chat.bot_welcomed = True
        await self._session.flush()
