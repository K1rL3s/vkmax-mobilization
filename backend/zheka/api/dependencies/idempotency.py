from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import Depends, Header
from fastapi.routing import APIRoute
from starlette.requests import Request

from zheka.api.dependencies.current_account import CurrentAccountDep
from zheka.api.schemas.base import BaseSchema
from zheka.core.ids import UserId
from zheka.infra.database.repos.idempotency import IdempotencyRepo

HEADER = "Idempotency-Key"


class Idempotency:
    __slots__ = ("_key", "_repo", "_route", "_user_id")

    def __init__(
        self,
        repo: IdempotencyRepo,
        user_id: UserId,
        key: UUID | None,
        route: str,
    ) -> None:
        self._repo = repo
        self._user_id = user_id
        self._key = key
        self._route = route

    async def replay[SchemaT: BaseSchema](
        self,
        schema: type[SchemaT],
    ) -> SchemaT | None:
        if self._key is None:
            return None
        saved = await self._repo.claim(self._user_id, self._key, self._route)
        return None if saved is None else schema.model_validate(saved)

    async def save(self, response: BaseSchema) -> None:
        if self._key is None:
            return
        await self._repo.save(
            self._user_id,
            self._key,
            response.model_dump(mode="json"),
        )


@inject
async def get_idempotency(
    *,
    request: Request,
    current_account: CurrentAccountDep,
    idempotency_repo: FromDishka[IdempotencyRepo],
    key: Annotated[UUID | None, Header(alias=HEADER)] = None,
) -> Idempotency:
    route: APIRoute = request.scope["route"]
    return Idempotency(idempotency_repo, current_account.user_id, key, route.path)


IdempotencyDep = Annotated[Idempotency, Depends(get_idempotency)]
