from dishka import BaseScope, Provider, Scope, provide_all

from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
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
    )
