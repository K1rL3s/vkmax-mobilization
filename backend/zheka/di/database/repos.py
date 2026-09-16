from dishka import BaseScope, Provider, Scope


class ReposProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST
