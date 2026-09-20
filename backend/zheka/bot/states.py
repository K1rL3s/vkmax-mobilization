from maxo.fsm import State, StatesGroup

from zheka.core.models import User


class Consent(StatesGroup):
    ask = State()


class Menu(StatesGroup):
    main = State()


def entry_state(user: User) -> State:
    # каждая дорога в дом начинается с согласия на обработку ПД. Живет в bot/,
    # а не методом User: состояния диалогов - слой бота, core/ о них не знает
    return Menu.main if user.consent_at is not None else Consent.ask


class Onboarding(StatesGroup):
    method = State()
    city = State()
    street = State()
    house = State()
    geo = State()
    flat = State()


class NewRequest(StatesGroup):
    category = State()
    description = State()
    photo = State()
    confirm = State()
    sent = State()
