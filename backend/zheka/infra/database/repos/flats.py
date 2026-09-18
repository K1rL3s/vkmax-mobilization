from collections.abc import Collection, Sequence
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from zheka.core.enums import VerificationStatus
from zheka.core.ids import FlatId, HouseId, OrgId, UserId, VerificationRequestId
from zheka.infra.database.models import VerificationRequest
from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.repos.scopes import scoped_to_org
from zheka.infra.database.tables.houses import flats_table
from zheka.infra.database.tables.meters import meters_table
from zheka.infra.database.tables.residents import flat_verification_requests_table


def _joined_to_flats() -> Select[tuple[VerificationRequest]]:
    # у запроса подтверждения нет своего дома, он достается через квартиру:
    # без этого соединения scoped_to_org не к чему применить
    return select(VerificationRequest).join(
        flats_table,
        flats_table.c.id == flat_verification_requests_table.c.flat_id,
    )


class FlatsRepo(BaseAlchemyRepo):
    async def get_verification_request(
        self,
        verification_id: VerificationRequestId,
        org_id: OrgId,
    ) -> VerificationRequest | None:
        # verification_id приходит из пути, поэтому запрос сужается до домов
        # организации: чужой запрос отвечает 404, а не 403
        stmt = scoped_to_org(
            _joined_to_flats().where(
                flat_verification_requests_table.c.id == verification_id,
            ),
            flats_table.c.house_id,
            org_id,
        )
        # аннотация обязательна: VerificationRequest отображен императивно,
        # и scalar() для такой сущности возвращает Any
        request: VerificationRequest | None = await self._session.scalar(stmt)
        return request

    async def get_latest_request(
        self,
        user_id: UserId,
        flat_id: FlatId,
    ) -> VerificationRequest | None:
        stmt = (
            select(VerificationRequest)
            .where(
                flat_verification_requests_table.c.user_id == user_id,
                flat_verification_requests_table.c.flat_id == flat_id,
            )
            .order_by(flat_verification_requests_table.c.id.desc())
            .limit(1)
        )
        request: VerificationRequest | None = await self._session.scalar(stmt)
        return request

    async def list_latest_requests(
        self,
        user_id: UserId,
        flat_ids: Collection[FlatId],
    ) -> Sequence[VerificationRequest]:
        if not flat_ids:
            return []
        # DISTINCT ON оставляет от каждой квартиры одну, самую свежую запись:
        # житель с тремя привязками стоит одного запроса, а не трех
        stmt = (
            select(VerificationRequest)
            .where(
                flat_verification_requests_table.c.user_id == user_id,
                flat_verification_requests_table.c.flat_id.in_(flat_ids),
            )
            .distinct(flat_verification_requests_table.c.flat_id)
            .order_by(
                flat_verification_requests_table.c.flat_id,
                flat_verification_requests_table.c.id.desc(),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def list_verification_requests(
        self,
        org_id: OrgId,
        status: VerificationStatus | None,
        house_id: HouseId | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[VerificationRequest], int]:
        stmt = scoped_to_org(_joined_to_flats(), flats_table.c.house_id, org_id)
        if status is not None:
            stmt = stmt.where(flat_verification_requests_table.c.status == status)
        if house_id is not None:
            stmt = stmt.where(flats_table.c.house_id == house_id)

        total = await self._count(stmt)
        page_stmt = (
            stmt.order_by(flat_verification_requests_table.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(page_stmt)
        return result.scalars().all(), total

    async def add_verification_request(
        self,
        flat_id: FlatId,
        user_id: UserId,
        account_no: str,
        comment: str | None,
    ) -> VerificationRequest | None:
        # None означает, что заявка по этой квартире уже ждет решения.
        # Частичный уникальный индекс разводит два параллельных нажатия, а
        # ON CONFLICT вместо исключения оставляет транзакцию вызывающего живой
        stmt = (
            pg_insert(VerificationRequest)
            .values(
                flat_id=flat_id,
                user_id=user_id,
                account_no=account_no,
                comment=comment,
                status=VerificationStatus.PENDING,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    flat_verification_requests_table.c.user_id,
                    flat_verification_requests_table.c.flat_id,
                ],
                index_where=flat_verification_requests_table.c.status
                == VerificationStatus.PENDING,
            )
            .returning(VerificationRequest)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def decide_verification_request(
        self,
        request: VerificationRequest,
        status: VerificationStatus,
        by: UserId,
        at: datetime,
        reason: str | None,
    ) -> None:
        request.status = status
        request.decided_by = by
        request.decided_at = at
        request.reason = reason
        await self._session.flush()

    async def count_pending_verifications(self, house_id: HouseId) -> int:
        flat_ids = select(flats_table.c.id).where(flats_table.c.house_id == house_id)
        stmt = (
            select(func.count())
            .select_from(flat_verification_requests_table)
            .where(
                flat_verification_requests_table.c.flat_id.in_(flat_ids),
                flat_verification_requests_table.c.status == VerificationStatus.PENDING,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_meters(self, flat_id: FlatId) -> int:
        # счетчики заводит блок 10, здесь нужно только их число на карточке
        stmt = (
            select(func.count())
            .select_from(meters_table)
            .where(meters_table.c.flat_id == flat_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
