from collections.abc import Sequence
from datetime import date, datetime

from zheka.base import ZhekaType
from zheka.core.enums import RequestPlace
from zheka.core.ids import AccessRequestId
from zheka.core.models import Request
from zheka.core.services.visit_card import VisitData
from zheka.infra.database.repos.requests import OPEN_STATUSES

MAX_WINDOWS = 5
MIN_MINUTES = 15
MAX_MINUTES = 240

NOT_PERSONAL = "Время визита предлагают только по личной заявке"
NO_AUTHOR = "У заявки нет жителя в MAX: о визите договоритесь по телефону"
NOT_OPEN = "Время визита предлагают, пока заявка не сдана на приемку"
NO_VISIT = "У заявки нет визита"
WINDOWS_COUNT = f"Предложите от 1 до {MAX_WINDOWS} окон"
BAD_MINUTES = f"Окно визита - от {MIN_MINUTES} до {MAX_MINUTES} минут"
DUPLICATE_WINDOWS = "Окна визита начинаются в одно и то же время"
WINDOW_OFF_DATE = "Окна визита должны быть в один день"
PAST_WINDOW = "Окно визита уже началось или прошло"
WINDOW_NOT_FOUND = "Окно визита не найдено"
VISIT_NOT_FOUND = "Визит не найден"
REQUEST_CLOSED = "Заявка уже не ждет визита"
VISIT_CANCELED = "УК отменила этот визит"
VISIT_REPLACED = "УК предложила другое время: выберите его в новом сообщении"
VISIT_UNDER_WAY = "Визит уже начался: поменять время нельзя"


class VisitDraft(ZhekaType):
    date: date
    starts: Sequence[datetime]
    minutes: int


def stale_visit(
    request: Request,
    visit: VisitData | None,
    visit_id: AccessRequestId,
) -> str | None:
    if request.status not in OPEN_STATUSES:
        return REQUEST_CLOSED
    if visit is None:
        return VISIT_CANCELED
    if visit.id != visit_id:
        return VISIT_REPLACED
    return None


def visit_refusal(request: Request) -> str | None:
    if request.place is not RequestPlace.FLAT or request.flat_id is None:
        return NOT_PERSONAL
    if request.author_user_id is None:
        return NO_AUTHOR
    if request.status not in OPEN_STATUSES:
        return NOT_OPEN
    return None
