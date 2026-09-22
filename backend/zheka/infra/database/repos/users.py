from collections.abc import Collection, Sequence
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.errors import EntityNotFound
from zheka.core.ids import MaxChatId, MaxUserId, UserId
from zheka.infra.database.models import User, fresh_timestamp
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.users import users_table


class UsersRepo(BaseAlchemyRepo):
    async def upsert_by_max_id(
        self,
        max_user_id: MaxUserId,
        name: str,
        username: str | None,
        max_chat_id: MaxChatId | None = None,
    ) -> User:
        insert = pg_insert(User).values(
            max_user_id=max_user_id,
            name=name,
            username=username,
            max_chat_id=max_chat_id,
        )
        stmt = insert.on_conflict_do_update(
            index_elements=[users_table.c.max_user_id],
            set_={
                "name": name,
                "username": username,
                "max_chat_id": func.coalesce(
                    insert.excluded.max_chat_id,
                    users_table.c.max_chat_id,
                ),
                "bot_stopped_at": case(
                    (
                        insert.excluded.max_chat_id.is_(None),
                        users_table.c.bot_stopped_at,
                    ),
                    else_=None,
                ),
                "updated_at": fresh_timestamp(),
            },
        ).returning(User)
        result = await self._session.execute(
            stmt,
            execution_options={"populate_existing": True},
        )
        return result.scalar_one()

    async def get_by_id(self, user_id: UserId) -> User | None:
        stmt = select(User).where(users_table.c.id == user_id)
        user: User | None = await self._session.scalar(stmt)
        return user

    async def get_by_max_id(self, max_user_id: MaxUserId) -> User | None:
        stmt = select(User).where(users_table.c.max_user_id == max_user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_consent(self, user_id: UserId, version: str) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")
        user.consent_version = version
        user.consent_at = datetime.now(UTC)
        await self._session.flush()

    async def set_bot_stopped(self, max_user_id: MaxUserId, at: datetime) -> None:
        user = await self.get_by_max_id(max_user_id)
        if user is None:
            raise EntityNotFound("Пользователь не найден")
        user.bot_stopped_at = at

    async def list_by_ids(self, user_ids: Collection[UserId]) -> Sequence[User]:
        if not user_ids:
            return []
        stmt = select(User).where(users_table.c.id.in_(user_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()
