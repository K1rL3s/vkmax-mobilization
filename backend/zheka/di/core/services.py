from dishka import BaseScope, Provider, Scope


class ServicesProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST
