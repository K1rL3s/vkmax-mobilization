import asyncio
import secrets
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from dishka import AsyncContainer
from maxo.dialogs.test_tools import BotClient
from maxo.dialogs.test_tools.bot_client import FakeBot
from maxo.enums import ChatType
from maxo.types import Message, MessageBody, Recipient
from maxo.types.send_message_result import SendMessageResult
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from taskiq import InMemoryBroker

from tests.conftest import RecordingBroker, make_config
from tests.test_bot import _run
from tests.test_seed import FILES, NOW, _demo

from zheka.bot import BotSetup
from zheka.bot.handlers.commands.start import SEEDING_TEXT
from zheka.broker.task_names import TaskName
from zheka.broker.tasks import seed as seed_task
from zheka.broker.tasks.seed import ALREADY_SEEDED, SEEDED, seed_demo
from zheka.core.enums import NotificationCategory
from zheka.core.ids import MaxUserId, UserId
from zheka.infra.database.repos.users import UsersRepo
from zheka.seed.demo import SEED_LOCK, seed

WAITER_TIMEOUT = 30.0
MID = "seed-1"
CHAT_ID = 1


async def test_seed_command_queues_the_task_and_answers_at_once(
    bot_container: AsyncContainer,  # noqa: ARG001
    bot_session: AsyncSession,
    bot_setup: BotSetup,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, Any]] = []
    original = fake_bot.send_message

    async def recording(**kwargs: Any) -> Any:
        sent.append(kwargs)
        await original(**kwargs)
        return SendMessageResult(
            message=Message(
                recipient=Recipient(chat_type=ChatType.DIALOG, chat_id=CHAT_ID),
                timestamp=datetime.now(UTC),
                body=MessageBody(mid=MID, seq=1, text=kwargs["text"]),
            ),
        )

    monkeypatch.setattr(fake_bot, "send_message", recording)
    max_user_id = MaxUserId(secrets.randbits(40))
    client = BotClient(
        bot_setup.dp,
        user_id=max_user_id,
        chat_id=max_user_id,
        bot=fake_bot,
    )

    await client.send("/seed")

    user = await UsersRepo(bot_session).get_by_max_id(max_user_id)
    assert user is not None
    assert [message["text"] for message in sent] == [SEEDING_TEXT]
    assert bot_broker.enqueued(TaskName.SEED_DEMO)[-1] == {
        "user_id": user.id,
        "mid": MID,
        "chat_id": CHAT_ID,
    }


@pytest.mark.parametrize(
    ("seeded", "reply"),
    [(True, SEEDED), (False, ALREADY_SEEDED)],
    ids=["seeded", "already"],
)
async def test_the_task_seeds_now_and_tells_the_caller(
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
    monkeypatch: pytest.MonkeyPatch,
    seeded: bool,
    reply: str,
) -> None:
    calls: list[tuple[Path, datetime]] = []

    async def stub(_session: Any, _demo: Any, files_dir: Path, now: datetime) -> bool:
        calls.append((files_dir, now))
        return seeded

    monkeypatch.setattr(seed_task, "seed", stub)
    queued = len(bot_broker.messages)
    user_id = UserId(secrets.randbits(30))

    before = datetime.now(UTC)
    await _run(task_broker, seed_demo, user_id=user_id)

    [(files_dir, now)] = calls
    assert files_dir == Path(make_config().files.dir)
    assert before <= now <= datetime.now(UTC)
    [message] = bot_broker.messages[queued:]
    assert message.task_name == TaskName.SEND_TO_USER.value
    assert message.kwargs == {
        "user_id": user_id,
        "text": reply,
        "category": NotificationCategory.ANNOUNCEMENTS.value,
        "mandatory": True,
        "app_button": None,
        "app_path": None,
    }


async def test_the_task_turns_the_waiting_message_into_the_result(
    task_broker: InMemoryBroker,
    bot_broker: RecordingBroker,
    fake_bot: FakeBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stub(*_: Any) -> bool:
        return True

    edits: list[dict[str, Any]] = []

    async def recording(**kwargs: Any) -> Any:
        edits.append(kwargs)
        return None

    monkeypatch.setattr(seed_task, "seed", stub)
    monkeypatch.setattr(fake_bot, "edit_message", recording, raising=False)
    queued = len(bot_broker.messages)

    await _run(
        task_broker,
        seed_demo,
        user_id=UserId(secrets.randbits(30)),
        mid=MID,
        chat_id=CHAT_ID,
    )

    assert [(edit["message_id"], edit["text"]) for edit in edits] == [(MID, SEEDED)]
    assert bot_broker.messages[queued:] == []


async def _waits_on_the_lock(
    engine: AsyncEngine,
    pid: int,
    pending: asyncio.Task[bool],
) -> bool:
    stmt = text(
        "SELECT count(*) FROM pg_locks"
        " WHERE locktype = 'advisory' AND NOT granted AND pid = :pid",
    ).bindparams(pid=pid)
    async with engine.connect() as observer, asyncio.timeout(WAITER_TIMEOUT):
        while not pending.done():
            if (await observer.execute(stmt)).scalar_one():
                return True
            await asyncio.sleep(0.05)
    return False


async def test_a_second_seed_waits_for_the_first(engine: AsyncEngine) -> None:
    async with engine.connect() as holder, engine.connect() as second:
        holder_transaction = await holder.begin()
        lock_stmt = select(func.pg_advisory_xact_lock(SEED_LOCK))
        await holder.execute(lock_stmt)
        second_transaction = await second.begin()
        pid_stmt = select(func.pg_backend_pid())
        pid = (await second.execute(pid_stmt)).scalar_one()
        async with AsyncSession(
            bind=second,
            join_transaction_mode="create_savepoint",
        ) as session:
            pending = asyncio.create_task(seed(session, _demo(session), FILES, NOW))
            try:
                waited = await _waits_on_the_lock(engine, pid, pending)
            finally:
                await holder_transaction.rollback()
                await pending
                await second_transaction.rollback()

    assert waited


def test_the_worker_import_registers_every_task() -> None:
    script = (
        "import zheka.broker.tasks\n"
        "from taskiq import async_shared_broker\n"
        "from zheka.broker.task_names import TaskName\n"
        "registered = async_shared_broker.get_all_tasks()\n"
        "print(sorted(name for name in TaskName if name.value not in registered))\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "[]"
