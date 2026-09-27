from typing import Annotated
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BaseError(BaseSchema):
    title: str
    detail: str


class ApiError[ErrorT: BaseError](BaseSchema):
    status: int
    ok: bool = False
    trace_id: UUID
    error: ErrorT


class OkResponse(BaseSchema):
    ok: bool = True


class Page[ItemT](BaseSchema):
    items: list[ItemT]
    total: int


Limit = Annotated[int, Query(ge=1, le=100, description="Размер страницы")]
Offset = Annotated[int, Query(ge=0, description="Сдвиг от начала списка")]
FreeText = Annotated[str, Field(max_length=4000)]
