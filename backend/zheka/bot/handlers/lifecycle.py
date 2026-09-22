from datetime import UTC, datetime

from dishka import FromDishka
from maxo import Router
from maxo.types import BotStopped, DialogMuted, DialogUnmuted

from zheka.core.enums import EventType
from zheka.core.models import User
from zheka.core.services.events import EventsService
from zheka.infra.database.repos.users import UsersRepo

router = Router(name=__name__)


@router.bot_stopped()
async def bot_stopped_handler(
    _update: BotStopped,
    user: User,
    users_repo: FromDishka[UsersRepo],
    events_service: FromDishka[EventsService],
) -> None:
    await users_repo.set_bot_stopped(user.max_user_id, datetime.now(UTC))
    await events_service.record(EventType.BOT_STOPPED, user_id=user.id)


@router.dialog_muted()
async def dialog_muted_handler(
    _update: DialogMuted,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    await events_service.record(EventType.BOT_MUTED, user_id=user.id)


@router.dialog_unmuted()
async def dialog_unmuted_handler(
    _update: DialogUnmuted,
    user: User,
    events_service: FromDishka[EventsService],
) -> None:
    await events_service.record(EventType.BOT_UNMUTED, user_id=user.id)
