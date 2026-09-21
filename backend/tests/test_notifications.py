import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from maxo.types.send_message_result import SendMessageResult
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import BrokerMessage

from tests.conftest import OrgHouseFlatUser, RecordingBroker, make_notifications_service

from zheka.broker.publisher import TaskPublisher
from zheka.broker.task_names import TaskName
from zheka.broker.tasks.notifications import _fan_out
from zheka.core.enums import (
    EventType,
    NotificationCategory,
    NotificationLevel,
    OrgRole,
    RequestCategory,
    RequestChannel,
    RequestGroupStatus,
    RequestStatus,
    ResidentRole,
)
from zheka.core.ids import MaxUserId, RequestGroupId, UserId
from zheka.core.notifications import DEFAULT_LEVEL, resolve_notify
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.events import EventsService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.request_status import transition_path
from zheka.infra.database.models import Event, Request, RequestGroup, User
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.database.tables.events import events_table
from zheka.infra.max import MaxSender

Fixture = Callable[..., Awaitable[OrgHouseFlatUser]]

TEXT = "Проверка связи"


class _FakeSender(MaxSender):
    __slots__ = ("sent",)

    def __init__(self) -> None:
        self.sent: list[tuple[MaxUserId | None, bool]] = []

    async def send_message(
        self,
        text: str,  # noqa: ARG002
        *,
        user_id: MaxUserId | None = None,
        notify: bool = False,
        **kwargs: Any,  # noqa: ARG002
    ) -> SendMessageResult | None:
        self.sent.append((user_id, notify))
        return None


async def _add_user(session: AsyncSession, name: str = "Сосед") -> User:
    user = User(max_user_id=MaxUserId(secrets.randbits(48)), name=name)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.parametrize(
    ("level", "mandatory", "expected"),
    [
        (NotificationLevel.SOUND, False, True),
        (NotificationLevel.SOUND, True, True),
        (NotificationLevel.SILENT, False, False),
        (NotificationLevel.SILENT, True, False),
        (NotificationLevel.OFF, False, None),
        (NotificationLevel.OFF, True, False),
    ],
)
def test_resolve_notify(
    level: NotificationLevel, mandatory: bool, expected: bool | None
) -> None:
    assert resolve_notify(level, mandatory=mandatory) is expected


async def test_levels_fill_missing_categories_with_default(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user()

    levels = await make_notifications_service(session).levels(data.user_id)

    assert levels == dict.fromkeys(NotificationCategory, DEFAULT_LEVEL)
    assert DEFAULT_LEVEL is NotificationLevel.SILENT


async def test_update_records_event_only_for_a_real_change(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user()
    service = make_notifications_service(session)

    await service.update(
        data.user_id, {NotificationCategory.REQUESTS: NotificationLevel.SOUND}
    )
    levels = await service.update(
        data.user_id, {NotificationCategory.REQUESTS: NotificationLevel.SOUND}
    )

    assert levels[NotificationCategory.REQUESTS] is NotificationLevel.SOUND
    assert levels[NotificationCategory.METERS] is DEFAULT_LEVEL
    stmt = select(Event).where(
        events_table.c.user_id == data.user_id,
        events_table.c.type == EventType.NOTIFICATION_SETTINGS_CHANGED.value,
    )
    result = await session.execute(stmt)
    assert len(result.scalars().all()) == 1


async def test_recipients_drop_bot_stopped_and_keep_muted(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user()
    muted = await _add_user(session, "Заглушивший")
    stopped = await _add_user(session, "Остановивший")
    stopped.bot_stopped_at = datetime.now(UTC)
    # мьют живет в MAX, у нас от него остается только событие
    session.add(Event(user_id=muted.id, type=EventType.BOT_MUTED.value, payload={}))
    await session.flush()

    recipients = await NotificationsRepo(session).recipients(
        [data.user_id, muted.id, stopped.id], NotificationCategory.ANNOUNCEMENTS
    )

    assert {recipient.user_id for recipient in recipients} == {data.user_id, muted.id}


async def test_recipient_without_settings_row_is_silent(
    session: AsyncSession, make_org_house_flat_user: Fixture
) -> None:
    data = await make_org_house_flat_user()

    recipients = await NotificationsRepo(session).recipients(
        [data.user_id], NotificationCategory.REQUESTS
    )

    assert [recipient.level for recipient in recipients] == [NotificationLevel.SILENT]


@pytest.mark.parametrize(
    ("level", "mandatory", "sent"),
    [
        (NotificationLevel.OFF, False, []),
        (NotificationLevel.OFF, True, [False]),
        (NotificationLevel.SOUND, False, [True]),
    ],
)
async def test_fan_out_sends_with_the_resolved_sound(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    level: NotificationLevel,
    mandatory: bool,
    sent: list[bool],
) -> None:
    data = await make_org_house_flat_user()
    repo = NotificationsRepo(session)
    await repo.set_level(data.user_id, NotificationCategory.REQUESTS, level)
    sender = _FakeSender()
    category = NotificationCategory.REQUESTS.value

    count = await _fan_out(sender, repo, [data.user_id], TEXT, category, mandatory)

    user = await UsersRepo(session).get_by_id(data.user_id)
    assert user is not None
    assert count == len(sent)
    assert sender.sent == [(user.max_user_id, flag) for flag in sent]


async def test_notify_user_reaches_the_broker(
    session: AsyncSession, broker: RecordingBroker, publisher: TaskPublisher
) -> None:
    make_notifications_service(session, publisher).notify_user(
        UserId(1), TEXT, category=NotificationCategory.REQUESTS, mandatory=True
    )

    await publisher.flush()
    assert broker.enqueued(TaskName.SEND_TO_USER) == [
        {"user_id": 1, "text": TEXT, "category": "requests", "mandatory": True}
    ]


def _admin_service(
    session: AsyncSession, publisher: TaskPublisher
) -> AdminRequestsService:
    return AdminRequestsService(
        RequestsRepo(session),
        HousesRepo(session),
        UsersRepo(session),
        OrgsRepo(session),
        GroupingService(RequestsRepo(session), EventsService(EventsRepo(session))),
        make_notifications_service(session, publisher),
        EventsService(EventsRepo(session)),
    )


async def _add_request(
    session: AsyncSession,
    data: OrgHouseFlatUser,
    group_id: RequestGroupId | None = None,
) -> Request:
    request = Request(
        house_id=data.house_id,
        flat_id=data.flat_id,
        author_user_id=data.user_id,
        category=RequestCategory.LEAK,
        description="Течет кран",
        status=RequestStatus.NEW,
        channel=RequestChannel.MINIAPP,
        group_id=group_id,
    )
    session.add(request)
    await session.flush()
    return request


async def _add_group(session: AsyncSession, data: OrgHouseFlatUser) -> RequestGroup:
    group = RequestGroup(
        house_id=data.house_id,
        category=RequestCategory.LEAK,
        window_started_at=datetime.now(UTC),
        status=RequestGroupStatus.OPEN,
    )
    session.add(group)
    await session.flush()
    return group


async def test_status_change_notifies_the_author_once(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(
        org_role=OrgRole.ADMIN, resident_role=ResidentRole.OWNER
    )
    request = await _add_request(session, data)
    service = _admin_service(session, publisher)

    await service.change_status(
        data.org_id, request.id, RequestStatus.ACCEPTED, None, data.user_id
    )

    await publisher.flush()
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert enqueued[0]["user_id"] == data.user_id
    assert enqueued[0]["mandatory"] is True
    assert "Принята" in enqueued[0]["text"]


async def test_group_catch_up_notifies_the_author_once(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(
        org_role=OrgRole.ADMIN, resident_role=ResidentRole.OWNER
    )
    group = await _add_group(session, data)
    # опоздавший участник идет из NEW в IN_PROGRESS двумя шагами, а житель
    # просил один ответ, а не пачку пушей
    request = await _add_request(session, data, group.id)
    assert len(transition_path(request.status, RequestStatus.IN_PROGRESS)) == 2

    await _admin_service(session, publisher).change_group_status(
        data.org_id, group.id, RequestStatus.IN_PROGRESS, "Сделаем завтра", data.user_id
    )

    await publisher.flush()
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert "В работе" in enqueued[0]["text"]
    assert "Сделаем завтра" in enqueued[0]["text"]


async def test_reply_reaches_the_author(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    data = await make_org_house_flat_user(
        org_role=OrgRole.ADMIN, resident_role=ResidentRole.OWNER
    )
    request = await _add_request(session, data)
    answer = "Слесарь придет во вторник"

    await _admin_service(session, publisher).reply(
        data.org_id, request.id, answer, data.user_id
    )

    await publisher.flush()
    enqueued = broker.enqueued(TaskName.SEND_TO_USER)
    assert len(enqueued) == 1
    assert enqueued[0]["user_id"] == data.user_id
    assert enqueued[0]["mandatory"] is True
    assert answer in enqueued[0]["text"]


class _FlakyBroker(RecordingBroker):
    # первый кик падает, дальше брокер работает как обычно
    def __init__(self) -> None:
        super().__init__()
        self.failed_once = False

    async def kick(self, message: BrokerMessage) -> None:
        if not self.failed_once:
            self.failed_once = True
            raise RuntimeError("редис недоступен")
        await super().kick(message)


async def test_flush_sends_each_task_once(
    broker: RecordingBroker, publisher: TaskPublisher
) -> None:
    publisher.publish(TaskName.SEND_TO_USER, user_id=1)

    await publisher.flush()
    await publisher.flush()

    assert len(broker.enqueued(TaskName.SEND_TO_USER)) == 1


async def test_one_failed_task_does_not_stop_the_rest() -> None:
    flaky = _FlakyBroker()
    publisher = TaskPublisher(flaky)
    publisher.publish(TaskName.SEND_TO_USER, user_id=1)
    publisher.publish(TaskName.SEND_TO_USER, user_id=2)

    await publisher.flush()

    assert [kwargs["user_id"] for kwargs in flaky.enqueued(TaskName.SEND_TO_USER)] == [
        2
    ]


async def test_group_catch_up_to_review_opens_one_card_per_member(
    session: AsyncSession,
    make_org_house_flat_user: Fixture,
    broker: RecordingBroker,
    publisher: TaskPublisher,
) -> None:
    # групповой переход - третья дорога на приемку: каждому автору по одной
    # карточке, и ни одного текста статуса с промежуточных шагов
    data = await make_org_house_flat_user(
        org_role=OrgRole.ADMIN, resident_role=ResidentRole.OWNER
    )
    group = await _add_group(session, data)
    first = await _add_request(session, data, group.id)
    second = await _add_request(session, data, group.id)

    await _admin_service(session, publisher).change_group_status(
        data.org_id, group.id, RequestStatus.ON_REVIEW, None, data.user_id
    )

    await publisher.flush()
    assert sorted(
        card["request_id"] for card in broker.enqueued(TaskName.SEND_REVIEW_CARD)
    ) == sorted([first.id, second.id])
    assert broker.enqueued(TaskName.SEND_TO_USER) == []
