from collections.abc import Collection, Sequence

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.base import ZhekaType
from zheka.core.enums import NotificationCategory, NotificationLevel
from zheka.core.ids import MaxUserId, UserId
from zheka.core.notifications import DEFAULT_LEVEL
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.users import notification_settings_table, users_table


class Recipient(ZhekaType):
    user_id: UserId
    max_user_id: MaxUserId
    level: NotificationLevel


class NotificationsRepo(BaseAlchemyRepo):
    async def get_levels(
        self, user_id: UserId
    ) -> dict[NotificationCategory, NotificationLevel]:
        stmt = select(
            notification_settings_table.c.category, notification_settings_table.c.level
        ).where(notification_settings_table.c.user_id == user_id)
        result = await self._session.execute(stmt)
        return dict(result.tuples().all())

    async def set_level(
        self, user_id: UserId, category: NotificationCategory, level: NotificationLevel
    ) -> bool:
        # хранится только то, что житель менял руками, отсюда апсерт. Ветка
        # DO UPDATE отсечена по тому же уровню, поэтому пустой RETURNING и
        # есть ответ "ничего не поменялось" - без чтения перед записью
        stmt = (
            pg_insert(notification_settings_table)
            .values(user_id=user_id, category=category, level=level)
            .on_conflict_do_update(
                index_elements=[
                    notification_settings_table.c.user_id,
                    notification_settings_table.c.category,
                ],
                set_={"level": level},
                where=notification_settings_table.c.level != level,
            )
            .returning(notification_settings_table.c.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def recipients(
        self, user_ids: Collection[UserId], category: NotificationCategory
    ) -> Sequence[Recipient]:
        # уровень приезжает тем же запросом: у жителя, который настройки не
        # трогал, строки нет, и за него отвечает DEFAULT_LEVEL
        joined = users_table.outerjoin(
            notification_settings_table,
            and_(
                notification_settings_table.c.user_id == users_table.c.id,
                notification_settings_table.c.category == category,
            ),
        )
        stmt = (
            select(
                users_table.c.id,
                users_table.c.max_user_id,
                notification_settings_table.c.level,
            )
            .select_from(joined)
            .where(
                users_table.c.id.in_(user_ids),
                # остановленному боту MAX отвечает 403, а не доставкой
                users_table.c.bot_stopped_at.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return [
            Recipient(
                user_id=UserId(user_id),
                max_user_id=MaxUserId(max_user_id),
                level=DEFAULT_LEVEL if level is None else level,
            )
            for user_id, max_user_id, level in result.tuples().all()
        ]
