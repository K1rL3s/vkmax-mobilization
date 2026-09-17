from dishka import BaseScope, Provider, Scope, provide

from zheka.config import FilesConfig, MaxConfig
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.houses import HousesService
from zheka.core.services.profile import ProfileService
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo


class ServicesProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST

    @provide
    def events_service(self, events_repo: EventsRepo) -> EventsService:
        return EventsService(events_repo)

    @provide(scope=Scope.APP)
    def files_service(self, config: FilesConfig, max_config: MaxConfig) -> FilesService:
        return FilesService(config, max_config.token)

    @provide
    def houses_service(
        self,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
    ) -> HousesService:
        return HousesService(
            houses_repo,
            residents_repo,
            orgs_repo,
            users_repo,
            events_service,
        )

    @provide
    def profile_service(
        self,
        users_repo: UsersRepo,
        residents_repo: ResidentsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
    ) -> ProfileService:
        return ProfileService(users_repo, residents_repo, houses_repo, orgs_repo)
