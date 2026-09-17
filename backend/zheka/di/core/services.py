from dishka import BaseScope, Provider, Scope, provide

from zheka.config import DeeplinksConfig, FilesConfig, MaxConfig
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.flats import FlatsService
from zheka.core.services.houses import HousesService
from zheka.core.services.moderation import ModerationService
from zheka.core.services.orgs import OrgsService
from zheka.core.services.profile import ProfileService
from zheka.core.services.requests import RequestsService
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.requests import RequestsRepo
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
        flats_repo: FlatsRepo,
        events_service: EventsService,
    ) -> HousesService:
        return HousesService(
            houses_repo,
            residents_repo,
            orgs_repo,
            users_repo,
            flats_repo,
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

    @provide
    def orgs_service(
        self,
        orgs_repo: OrgsRepo,
        invites_repo: InvitesRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
        deeplinks: DeeplinksConfig,
    ) -> OrgsService:
        return OrgsService(
            orgs_repo,
            invites_repo,
            houses_repo,
            users_repo,
            events_service,
            deeplinks,
        )

    @provide
    def moderation_service(
        self,
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        houses_repo: HousesRepo,
        events_service: EventsService,
    ) -> ModerationService:
        return ModerationService(
            residents_repo,
            users_repo,
            houses_repo,
            events_service,
        )

    @provide
    def flats_service(
        self,
        flats_repo: FlatsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        invites_repo: InvitesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        events_service: EventsService,
    ) -> FlatsService:
        return FlatsService(
            flats_repo,
            houses_repo,
            residents_repo,
            invites_repo,
            users_repo,
            orgs_repo,
            events_service,
        )

    @provide
    def requests_service(
        self,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        files_service: FilesService,
        events_service: EventsService,
    ) -> RequestsService:
        return RequestsService(
            requests_repo,
            houses_repo,
            residents_repo,
            users_repo,
            orgs_repo,
            files_service,
            events_service,
        )
