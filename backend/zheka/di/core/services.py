from dishka import BaseScope, Provider, Scope, provide

from zheka.config import FilesConfig, MaxConfig
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.infra.database.repos.events import EventsRepo


class ServicesProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST

    @provide
    def events_service(self, events_repo: EventsRepo) -> EventsService:
        return EventsService(events_repo)

    @provide(scope=Scope.APP)
    def files_service(self, config: FilesConfig, max_config: MaxConfig) -> FilesService:
        return FilesService(config, max_config.token)
