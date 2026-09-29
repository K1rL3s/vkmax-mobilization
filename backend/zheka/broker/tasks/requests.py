import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import Data, ShowMode
from maxo.fsm import State
from maxo.utils.upload_media import BufferedInputFile
from taskiq import async_shared_broker

from zheka.bot.dialog_data import ExecutorCardData, QuestionData, ReviewData
from zheka.bot.states import ExecutorCard, Question, Review
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.bot_requests import save_photos
from zheka.core import texts
from zheka.core.enums import NotificationCategory, RequestStatus
from zheka.core.errors import ZhekaError
from zheka.core.ids import RequestId, UserId
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.files import FilesService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.requests import RequestsService
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender
from zheka.infra.pdf import GjiComplaint

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
    files_service: FromDishka[FilesService],
    admin_requests_service: FromDishka[AdminRequestsService],
    user_id: UserId | None = None,
) -> None:
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
    if user_id is None:
        card = await admin_requests_service.executor_card(recipient, request_id)
        if card is None:
            return
        user = await users_repo.get_by_id(recipient)
        if user is not None:
            for attachment in card.issue_attachments:
                if files_service.is_video(attachment.path):
                    await sender.send_video(
                        files_service.path_of(attachment.path),
                        user,
                        request_id,
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
    names = await save_photos(bot, files_service, photo_urls)
    try:
        await admin_requests_service.executor_advance(
            user_id,
            request_id,
            RequestStatus.ON_REVIEW,
            names,
        )
    except ZhekaError as error:
        logger.warning("Результат по заявке %s не принят: %s", request_id, error)
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
    notify = bool(levels[NotificationCategory.REQUESTS].resolve_notify(mandatory=True))
    await sender.start_dialog(
        state,
        user,
        notify=notify,
        data=data,
        stack_id=stack_id,
        show_mode=show_mode,
    )


@async_shared_broker.task(
    task_name=TaskName.WATCH_REQUEST_DEADLINES.value,
    schedule=[{"cron": "*/5 * * * *"}],
)
@inject(patch_module=True)
async def watch_request_deadlines(
    requests_service: FromDishka[RequestsService],
) -> int:
    return await requests_service.watch_deadlines(datetime.now(UTC))


@async_shared_broker.task(task_name=TaskName.SEND_QUESTION_CARD.value)
@inject(patch_module=True)
async def send_question_card(
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
        Question.card,
        f"question-{request_id}",
        QuestionData(request_id=request_id).to_data(),
        ShowMode.SEND,
    )


@async_shared_broker.task(task_name=TaskName.SEND_GJI_PDF.value)
@inject(patch_module=True)
async def send_gji_pdf(
    user_id: UserId,
    request_id: RequestId,
    requests_service: FromDishka[RequestsService],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
) -> None:
    user = await users_repo.get_by_id(user_id)
    if user is None:
        return
    card = await requests_service.get_card(user_id, request_id)
    await sender.send_file(
        user,
        BufferedInputFile.file(
            GjiComplaint(card, datetime.now(UTC)).render(),
            f"zhaloba-{request_id}.pdf",
        ),
        texts.gji_pdf_sent(request_id),
    )
