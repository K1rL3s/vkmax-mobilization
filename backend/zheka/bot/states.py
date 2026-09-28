from maxo.fsm import State, StatesGroup

from zheka.core.models import User


class Consent(StatesGroup):
    ask = State()


class Menu(StatesGroup):
    main = State()
    emergency = State()


def entry_state(user: User) -> State:
    return Menu.main if user.consent_at is not None else Consent.ask


class Onboarding(StatesGroup):
    method = State()
    city = State()
    street = State()
    house = State()
    flat = State()


class NewRequest(StatesGroup):
    category = State()
    description = State()
    photo = State()
    confirm = State()
    sent = State()


class ExecutorCard(StatesGroup):
    card = State()
    result_photo = State()


class Review(StatesGroup):
    card = State()
    rating = State()
    rejection = State()


class ChatBinding(StatesGroup):
    house = State()
    code = State()
    rights = State()
    done = State()


class AccessSlots(StatesGroup):
    pick = State()
