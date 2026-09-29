from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from zheka.api.schemas.base import BaseSchema
from zheka.config import Config

router = APIRouter(tags=["Healthcheck"], route_class=DishkaRoute)


class HealthcheckResponse(BaseSchema):
    ok: bool
    commit: str = Field(
        description="Коммит, из которого собран образ API; dev без BUILD_COMMIT",
    )


@router.get("/healthcheck", summary="Проверка связи с базой и версия сборки")
async def healthcheck(
    session: FromDishka[AsyncSession],
    config: FromDishka[Config],
) -> HealthcheckResponse:
    await session.execute(text("SELECT 1"))
    return HealthcheckResponse(ok=True, commit=config.api.build_commit)
