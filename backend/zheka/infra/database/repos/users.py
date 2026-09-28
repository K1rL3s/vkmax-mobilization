from collections.abc import Collection, Sequence
from datetime import UTC, datetime

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import AppointmentStatus
from zheka.core.errors import EntityNotFound
from zheka.core.ids import MaxChatId, MaxUserId, UserId
from zheka.infra.database.models import Appointment, Request, User, fresh_timestamp
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.organizations import org_members_table
from zheka.infra.database.tables.reception import appointments_table
from zheka.infra.database.tables.requests import requests_table
from zheka.infra.database.tables.residents import (
    demand_signals_table,
    flat_verification_requests_table,
    residents_table,
    verification_revocations_table,
)
from zheka.infra.database.tables.users import (
    notification_settings_table,
    users_table,
)

FORGOTTEN_NAME = "Удаленный пользователь"


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
        stmt = select(User).where(users_table.c.id.in_(user_ids))
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def forget(self, user: User, max_user_id: MaxUserId) -> None:
        for table in (
            residents_table,
            flat_verification_requests_table,
            demand_signals_table,
            notification_settings_table,
            org_members_table,
            verification_revocations_table,
        ):
            stmt = delete(table).where(table.c.user_id == user.id)
            await self._session.execute(stmt)
        cancel = (
            update(Appointment)
            .where(
                appointments_table.c.user_id == user.id,
                appointments_table.c.status == AppointmentStatus.BOOKED,
                appointments_table.c.starts_at >= func.now(),
            )
            .values(status=AppointmentStatus.CANCELLED)
        )
        await self._session.execute(cancel)
        anonymize = (
            update(Request)
            .where(requests_table.c.author_user_id == user.id)
            .values(caller_name=None, caller_phone=None)
        )
        await self._session.execute(anonymize)
        user.max_user_id = max_user_id
        user.name = FORGOTTEN_NAME
        user.username = None
        user.max_chat_id = None
        user.consent_version = None
        user.consent_at = None
        user.phone = None
        user.phone_verified_at = None
        await self._session.flush()

    async def set_phone(
        self,
        user: User,
        phone: str | None,
        at: datetime | None,
    ) -> None:
        user.phone = phone
        user.phone_verified_at = at
        await self._session.flush()
