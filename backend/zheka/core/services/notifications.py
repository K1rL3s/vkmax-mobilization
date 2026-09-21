from collections.abc import Mapping, Sequence

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.core.enums import EventType, NotificationCategory, NotificationLevel
from zheka.core.ids import MaxChatId, RequestId, UserId
from zheka.core.notifications import DEFAULT_LEVEL, Buttons
from zheka.core.services.events import EventsService
from zheka.infra.database.repos.notifications import NotificationsRepo


class NotificationsService:
    __slots__ = ("_events", "_notifications", "_publisher")

    def __init__(
        self,
        notifications_repo: NotificationsRepo,
        publisher: TaskPublisher,
        events_service: EventsService,
    ) -> None:
        self._notifications = notifications_repo
        self._publisher = publisher
        self._events = events_service

    async def levels(
        self,
        user_id: UserId,
    ) -> dict[NotificationCategory, NotificationLevel]:
        # мини-апп рисует все три переключателя, поэтому недостающие строки
        # добираются дефолтом, а не пропускаются
        stored = await self._notifications.get_levels(user_id)
        return {
            category: stored.get(category, DEFAULT_LEVEL)
            for category in NotificationCategory
        }

    async def update(
        self,
        user_id: UserId,
        settings: Mapping[NotificationCategory, NotificationLevel],
    ) -> dict[NotificationCategory, NotificationLevel]:
        for category, level in settings.items():
            if not await self._notifications.set_level(user_id, category, level):
                continue
            await self._events.record(
                EventType.NOTIFICATION_SETTINGS_CHANGED,
                user_id=user_id,
                category=category.value,
                level=level.value,
            )
        return await self.levels(user_id)

    def notify_user(
        self,
        user_id: UserId,
        text: str,
        *,
        category: NotificationCategory,
        mandatory: bool,
        buttons: Buttons | None = None,
    ) -> None:
        # уровень уведомления разрешает сама задача, на месте отправки: так в
        # очереди лежит только id, а настройки читаются в момент доставки
        self._publisher.publish(
            TaskName.SEND_TO_USER,
            user_id=user_id,
            text=text,
            category=category.value,
            mandatory=mandatory,
            buttons=buttons,
        )

    def notify_users(
        self,
        user_ids: Sequence[UserId],
        text: str,
        *,
        category: NotificationCategory,
        mandatory: bool,
        buttons: Buttons | None = None,
    ) -> None:
        if not user_ids:
            return
        self._publisher.publish(
            TaskName.BROADCAST_TO_USERS,
            user_ids=list(user_ids),
            text=text,
            category=category.value,
            mandatory=mandatory,
            buttons=buttons,
        )

    def notify_chats(
        self,
        chat_ids: Sequence[MaxChatId],
        text: str,
        *,
        buttons: Buttons | None = None,
    ) -> None:
        if not chat_ids:
            return
        self._publisher.publish(
            TaskName.BROADCAST_TO_CHATS,
            chat_ids=list(chat_ids),
            text=text,
            buttons=buttons,
        )

    def open_executor_card(
        self,
        request_id: RequestId,
        user_id: UserId | None = None,
    ) -> None:
        # карточка - окно диалога, а не текст: получателя и его уровень
        # задача найдет сама, по заявке, уже после коммита. user_id - это
        # перерисовка для того, кто сам нажал, а не весть назначенному
        self._publisher.publish(
            TaskName.SEND_EXECUTOR_CARD,
            request_id=request_id,
            user_id=user_id,
        )

    def open_review_card(self, request_id: RequestId) -> None:
        self._publisher.publish(TaskName.SEND_REVIEW_CARD, request_id=request_id)
