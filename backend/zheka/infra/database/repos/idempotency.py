from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.errors import InvalidRequest
from zheka.core.ids import UserId
from zheka.infra.database.models import IdempotencyKey
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.idempotency import idempotency_keys_table

ANOTHER_ROUTE = "Ключ уже использован для другого действия"
STILL_RUNNING = "Запрос с этим ключом еще выполняется"


class IdempotencyRepo(BaseAlchemyRepo):
    async def claim(
        self,
        user_id: UserId,
        key: UUID,
        route: str,
    ) -> dict[str, Any] | None:
        claim_stmt = (
            pg_insert(IdempotencyKey)
            .values(user_id=user_id, key=key, route=route)
            .on_conflict_do_nothing(
                index_elements=[
                    idempotency_keys_table.c.user_id,
                    idempotency_keys_table.c.key,
                ],
            )
            .returning(IdempotencyKey)
        )
        claimed: IdempotencyKey | None = await self._session.scalar(claim_stmt)
        if claimed is not None:
            return None

        used_stmt = select(IdempotencyKey).where(
            idempotency_keys_table.c.user_id == user_id,
            idempotency_keys_table.c.key == key,
        )
        used: IdempotencyKey | None = await self._session.scalar(used_stmt)
        if used is None or used.route != route:
            raise InvalidRequest(ANOTHER_ROUTE)
        if used.response is None:
            raise InvalidRequest(STILL_RUNNING)
        return used.response

    async def save(
        self,
        user_id: UserId,
        key: UUID,
        response: dict[str, Any],
    ) -> None:
        stmt = (
            update(idempotency_keys_table)
            .where(
                idempotency_keys_table.c.user_id == user_id,
                idempotency_keys_table.c.key == key,
            )
            .values(response=response)
        )
        await self._session.execute(stmt)

    async def purge(self, before: datetime) -> int:
        stmt = (
            delete(idempotency_keys_table)
            .where(idempotency_keys_table.c.created_at < before)
            .returning(idempotency_keys_table.c.key)
        )
        result = await self._session.execute(stmt)
        return len(result.all())
