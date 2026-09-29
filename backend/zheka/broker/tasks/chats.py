import logging
from collections.abc import Sequence
from html import escape

from dishka.integrations.taskiq import FromDishka, inject
from maxo import Bot
from maxo.dialogs import ShowMode
from maxo.errors import MaxBotApiError, MaxBotNetworkError
from maxo.types.buttons import InlineButtons
from maxo.types.callback_button import CallbackButton
from maxo.types.link_button import LinkButton
from maxo.utils.deeplink import create_start_link, create_startapp_link
from taskiq import async_shared_broker

from zheka.bot.cards import VotePayload, app_link
from zheka.bot.dialog_data import ChatBindingData
from zheka.bot.states import ChatBinding
from zheka.broker.task_names import TaskName
from zheka.core.deeplinks import house_category_payload, house_payload
from zheka.core.enums import ChatCardKind
from zheka.core.errors import ZhekaError
from zheka.core.ids import HouseId, MaxChatId, MaxUserId
from zheka.core.models import ChatCard
from zheka.core.services.chat_cards import CardVote, ChatCardView, ChatCardsService
from zheka.core.services.chats import ChatsService, pins_text
from zheka.core.texts import (
    ANNOUNCEMENT_HASHTAG,
    CARD_HASHTAG,
    ME_TOO,
    POLL_HASHTAG,
    VOTE_IN_APP,
)
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.users import UsersRepo
from zheka.infra.max import MaxSender
from zheka.infra.max.sender import is_chat_admin

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 Здравствуйте, соседи! Я бот вашего дома. Сюда буду присылать "
    "объявления УК и напоминания об опросах, а заявки, показания и "
    "начисления - в личке со мной\n\n"
    f"🔎 Мои сообщения здесь легко найти поиском: {ANNOUNCEMENT_HASHTAG}, "
    f"{POLL_HASHTAG}, {CARD_HASHTAG}"
)
WELCOME_MEMBER_TEXT = (
    "👋 {name}, добро пожаловать в чат дома! Я бот дома: публикую здесь "
    "объявления УК и опросы. Заявки, показания счетчиков и начисления - в "
    "личке со мной. Нажмите «Присоединиться к дому», чтобы начать"
)
JOIN_HOUSE = "🏠 Присоединиться к дому"
PINS_HERE = "📌 Список закрепленных никуда не делся, он здесь"
LEFT_TEXT = (
    "🚪 Я вышел из чата «{title}»: привязать чат к дому может сотрудник УК, "
    "председатель или житель этого дома с кодом привязки. Найдите свой дом в "
    "меню и добавьте меня снова"
)


def chat_stack(chat_id: MaxChatId) -> str:
    return f"chat-{chat_id}"


@async_shared_broker.task(task_name=TaskName.ON_BOT_ADDED.value)
@inject(patch_module=True)
async def on_bot_added(
    chat_id: MaxChatId,
    is_channel: bool,
    initiator_max_user_id: MaxUserId,
    bot: FromDishka[Bot],
    chats_service: FromDishka[ChatsService],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
) -> None:
    user = None if is_channel else await users_repo.get_by_max_id(initiator_max_user_id)
    if user is None or user.max_chat_id is None or user.bot_stopped_at is not None:
        await bot.leave_chat(chat_id=chat_id)
        return

    title = (await bot.get_chat(chat_id=chat_id)).title or ""
    if await chats_service.bindable_houses(user.id):
        state, stack_id = ChatBinding.house, chat_stack(chat_id)
    elif await chats_service.is_resident(user.id):
        state, stack_id = ChatBinding.code, None
    else:
        await bot.leave_chat(chat_id=chat_id)
        await sender.send_message(
            LEFT_TEXT.format(title=escape(title)),
            user_id=user.max_user_id,
        )
        return

    await chats_service.on_bot_added(chat_id, title)
    await sender.start_dialog(
        state,
        user,
        notify=False,
        data=ChatBindingData(chat_id=int(chat_id), title=title).to_data(),
        stack_id=stack_id,
        show_mode=ShowMode.SEND,
    )


@async_shared_broker.task(task_name=TaskName.WELCOME_CHAT.value)
@inject(patch_module=True)
async def welcome_chat(
    chat_id: MaxChatId,
    house_id: HouseId,
    bot: FromDishka[Bot],
    sender: FromDishka[MaxSender],
    member: str | None = None,
) -> None:
    text = (
        WELCOME_TEXT
        if member is None
        else WELCOME_MEMBER_TEXT.format(name=escape(member))
    )
    await sender.send_message(
        text,
        chat_id=chat_id,
        notify=False,
        keyboard=_join_keyboard(bot, house_id),
    )


@async_shared_broker.task(task_name=TaskName.SYNC_CHAT_PINS.value)
@inject(patch_module=True)
async def sync_chat_pins(
    chat_id: MaxChatId,
    notify: bool,
    bot: FromDishka[Bot],
    chats_service: FromDishka[ChatsService],
    chats_repo: FromDishka[ChatsRepo],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
    resend: bool = False,
) -> None:
    listed = await chats_service.pin_list(chat_id)
    if listed is None:
        return
    chat = listed.chat
    mid = chat.pins_mid
    if not listed.pins:
        if mid is None:
            return
        await chats_repo.set_pins_mid(chat, None)
        if not await sender.delete_message(chat_id, mid):
            await recheck_chat_rights(chat_id, bot, chats_service, users_repo, sender)
        return

    text = pins_text(chat_id, listed.pins)
    keyboard = _join_keyboard(bot, listed.house_id)
    if (
        mid is not None
        and not resend
        and await sender.edit_message(chat_id, mid, text, keyboard)
    ):
        if not notify:
            if not await sender.is_pinned(chat_id, mid):
                await sender.send_message(PINS_HERE, chat_id=chat_id, reply_to=mid)
            return
    else:
        sent = await sender.send_message(
            text,
            chat_id=chat_id,
            notify=False,
            keyboard=keyboard,
        )
        if sent is None:
            await recheck_chat_rights(chat_id, bot, chats_service, users_repo, sender)
            return
        old, mid = mid, sent.message.body.mid
        await chats_repo.set_pins_mid(chat, mid)
        if old is not None:
            await sender.delete_message(chat_id, old)
    if not await sender.pin_message(chat_id, mid, notify=notify):
        await recheck_chat_rights(chat_id, bot, chats_service, users_repo, sender)


@async_shared_broker.task(task_name=TaskName.SYNC_CHAT_CARD.value)
@inject(patch_module=True)
async def sync_chat_card(
    kind: ChatCardKind,
    ref_id: int,
    post: bool,
    bot: FromDishka[Bot],
    cards: FromDishka[ChatCardsService],
    chats_service: FromDishka[ChatsService],
    chats_repo: FromDishka[ChatsRepo],
    users_repo: FromDishka[UsersRepo],
    sender: FromDishka[MaxSender],
) -> None:
    chats = await chats_repo.lock_for_card(kind, ref_id)
    view = await cards.render(kind, ref_id) if chats else None
    if view is None:
        return
    keyboard = _card_keyboard(bot, view)
    for chat in chats:
        chat_id = chat.chat_id
        card = await chats_repo.get_card(chat_id, kind, ref_id)
        if card is not None:
            done = await sender.edit_message(chat_id, card.mid, view.text, keyboard)
        elif post:
            sent = await sender.send_message(
                view.text,
                chat_id=chat_id,
                notify=False,
                keyboard=keyboard,
            )
            done = sent is not None
            if sent is not None:
                mid = sent.message.body.mid
                await chats_repo.add_card(
                    ChatCard(chat_id=chat_id, kind=kind, ref_id=ref_id, mid=mid),
                )
        else:
            continue
        if not done:
            await recheck_chat_rights(chat_id, bot, chats_service, users_repo, sender)


def _card_keyboard(bot: Bot, view: ChatCardView) -> list[Sequence[InlineButtons]]:
    keyboard: list[Sequence[InlineButtons]] = [
        [CallbackButton(text=vote.text, payload=_vote_payload(vote))]
        for vote in view.votes
    ]
    if view.app_path is not None:
        keyboard.extend(app_link(bot, VOTE_IN_APP, view.app_path) or [])
    if view.me_too is not None:
        payload = house_category_payload(view.house_id, view.me_too)
        url = create_startapp_link(bot, payload)
        keyboard.append([LinkButton(text=ME_TOO, url=url)])
    if view.join:
        keyboard.extend(_join_keyboard(bot, view.house_id))
    return keyboard


def _vote_payload(vote: CardVote) -> str:
    return VotePayload(poll_id=vote.poll_id, option_id=vote.option_id).pack()


async def recheck_chat_rights(
    chat_id: MaxChatId,
    bot: Bot,
    chats_service: ChatsService,
    users_repo: UsersRepo,
    sender: MaxSender,
) -> None:
    try:
        is_admin = await is_chat_admin(bot, chat_id)
        chat = await chats_service.set_admin(chat_id, is_admin)
    except (MaxBotApiError, MaxBotNetworkError, ZhekaError):
        logger.exception("Права бота в чате %s не перепроверены", chat_id)
        return
    binder = (
        None
        if is_admin or chat.bound_by is None
        else await users_repo.get_by_id(chat.bound_by)
    )
    if binder is None:
        return
    await sender.start_dialog(
        ChatBinding.rights,
        binder,
        notify=True,
        data=ChatBindingData(chat_id=int(chat_id), title=chat.title or "").to_data(),
        stack_id=chat_stack(chat_id),
        show_mode=ShowMode.SEND,
    )


def _join_keyboard(bot: Bot, house_id: HouseId) -> list[list[LinkButton]]:
    url = create_start_link(bot, house_payload(house_id))
    return [[LinkButton(text=JOIN_HOUSE, url=url)]]
