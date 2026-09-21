import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import Data, ShowMode
from maxo.fsm import State
from taskiq import async_shared_broker

from zheka.bot.dialog_data import ExecutorCardData, ReviewData
from zheka.bot.states import ExecutorCard, Review
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.bot_requests import save_photos
from zheka.core.enums import NotificationCategory, RequestStatus
from zheka.core.errors import ZhekaError
from zheka.core.ids import RequestId, UserId
from zheka.core.notifications import resolve_notify
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.files import FilesService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.requests import RequestsService
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender

logger = logging.getLogger(__name__)


@async_shared_broker.task(
    task_name=TaskName.AUTO_CLOSE_REVIEWED_REQUESTS.value,
    schedule=[{"cron": "* * * * *"}],
)
@inject(patch_module=True)
async def auto_close_reviewed_requests(
    requests_service: FromDishka[RequestsService],
) -> int:
    return await requests_service.auto_close(datetime.now(UTC))


@async_shared_broker.task(task_name=TaskName.SEND_EXECUTOR_CARD.value)
@inject(patch_module=True)
async def send_executor_card(
    request_id: RequestId,
    requests_repo: FromDishka[RequestsRepo],
    users_repo: FromDishka[UsersRepo],
    notifications_service: FromDishka[NotificationsService],
    sender: FromDishka[MaxSender],
    user_id: UserId | None = None,
) -> None:
    # без user_id - новость назначенному, с user_id - перерисовка для того,
    # кто нажал сам, даже если заявку уже передали другому
    request = await requests_repo.get(request_id)
    if request is None:
        return
    recipient = request.executor_user_id if user_id is None else user_id
    if recipient is None:
        return
    await open_card(
        users_repo,
        notifications_service,
        sender,
        recipient,
        ExecutorCard.card,
        f"executor-{request_id}",
        ExecutorCardData(request_id=request_id).to_data(),
        ShowMode.SEND if user_id is None else None,
    )


@async_shared_broker.task(task_name=TaskName.SEND_REVIEW_CARD.value)
@inject(patch_module=True)
async def send_review_card(
    request_id: RequestId,
    requests_repo: FromDishka[RequestsRepo],
    users_repo: FromDishka[UsersRepo],
    notifications_service: FromDishka[NotificationsService],
    sender: FromDishka[MaxSender],
) -> None:
    request = await requests_repo.get(request_id)
    if request is None or request.author_user_id is None:
        return
    await open_card(
        users_repo,
        notifications_service,
        sender,
        request.author_user_id,
        Review.card,
        f"review-{request_id}",
        ReviewData(request_id=request_id).to_data(),
        ShowMode.SEND,
    )


@async_shared_broker.task(task_name=TaskName.ATTACH_RESULT_PHOTO.value)
@inject(patch_module=True)
async def attach_result_photo(
    user_id: UserId,
    request_id: RequestId,
    photo_urls: Sequence[str],
    bot: FromDishka[Bot],
    files_service: FromDishka[FilesService],
    admin_requests_service: FromDishka[AdminRequestsService],
    notifications_service: FromDishka[NotificationsService],
) -> None:
    # ponytail: фото, сохраненные перед отказом, остаются на диске без
    # ссылок, как и в create_bot_request; чистить, если диск станет тесен
    names = await save_photos(bot, files_service, photo_urls)
    try:
        await admin_requests_service.executor_advance(
            user_id, request_id, RequestStatus.ON_REVIEW, names
        )
    except ZhekaError as error:
        # отказ ничего не записал, а карточку исполнитель все равно должен увидеть
        logger.warning("Результат по заявке %s не принят: %s", request_id, error)
    # геттер окна читает в другой сессии и до коммита увидел бы старый статус
    notifications_service.open_executor_card(request_id, user_id)


async def open_card(
    users_repo: UsersRepo,
    notifications_service: NotificationsService,
    sender: MaxSender,
    user_id: UserId,
    state: State,
    stack_id: str,
    data: Data,
    show_mode: ShowMode | None,
) -> None:
    user = await users_repo.get_by_id(user_id)
    if user is None:
        return
    levels = await notifications_service.levels(user_id)
    # карточка обязательна: при OFF гаснет только звук, None тут не бывает
    notify = bool(resolve_notify(levels[NotificationCategory.REQUESTS], mandatory=True))
    await sender.start_dialog(
        state, user, notify=notify, data=data, stack_id=stack_id, show_mode=show_mode
    )
