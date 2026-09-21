from dishka import BaseScope, Provider, Scope, provide_all

from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo


class ReposProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST

    repos = provide_all(
        UsersRepo,
        ResidentsRepo,
        HousesRepo,
        OrgsRepo,
        EventsRepo,
        InvitesRepo,
        FlatsRepo,
        RequestsRepo,
        MetersRepo,
        ChargesRepo,
        PollsRepo,
        NotificationsRepo,
        ChatsRepo,
        AnnouncementsRepo,
        ReceptionRepo,
        AccessRepo,
        AnalyticsRepo,
    )
