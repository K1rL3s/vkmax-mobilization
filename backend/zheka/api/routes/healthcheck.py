from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zheka.api.schemas.base import BaseSchema

router = APIRouter(tags=["Healthcheck"], route_class=DishkaRoute)


class HealthcheckResponse(BaseSchema):
    ok: bool


@router.get("/healthcheck", summary="Проверка связи с базой")
async def healthcheck(session: FromDishka[AsyncSession]) -> HealthcheckResponse:
    await session.execute(text("SELECT 1"))
    return HealthcheckResponse(ok=True)
