from dishka import BaseScope, Provider, Scope, provide

from zheka.core.services.events import EventsService
from zheka.infra.database.repos.events import EventsRepo


class ServicesProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST

    @provide
    def events_service(self, events_repo: EventsRepo) -> EventsService:
        return EventsService(events_repo)
