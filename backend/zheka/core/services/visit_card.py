from collections.abc import Sequence
from datetime import datetime

from zheka.base import ZhekaType
from zheka.core.enums import RequestStatus
from zheka.core.ids import AccessRequestId, AccessSlotId
from zheka.core.models import AccessRequest, Request
from zheka.infra.database.repos.access import AccessRepo


class VisitWindow(ZhekaType):
    id: AccessSlotId
    starts_at: datetime
    minutes: int


class VisitData(ZhekaType):
    visit: AccessRequest
    windows: Sequence[VisitWindow]
    slot_id: AccessSlotId | None

    @property
    def id(self) -> AccessRequestId:
        return self.visit.id

    @property
    def picked(self) -> VisitWindow | None:
        return next(
            (window for window in self.windows if window.id == self.slot_id),
            None,
        )

    def under_way(self, now: datetime) -> bool:
        picked = self.picked
        return picked is not None and picked.starts_at <= now


async def visit_of(access_repo: AccessRepo, request: Request) -> VisitData | None:
    if request.status is RequestStatus.DONE:
        return None
    visit = await access_repo.current_visit(request.id)
    if visit is None:
        return None
    return await visit_data(access_repo, visit)


async def visit_data(access_repo: AccessRepo, visit: AccessRequest) -> VisitData:
    slots = await access_repo.list_slots([visit.id])
    target = await access_repo.visit_target(visit.id)
    return VisitData(
        visit=visit,
        windows=[
            VisitWindow(id=slot.id, starts_at=slot.starts_at, minutes=slot.minutes or 0)
            for slot in slots
        ],
        slot_id=target.slot_id,
    )
