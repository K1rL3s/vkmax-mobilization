from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BaseError(BaseSchema):
    title: str
    detail: str


class ApiError[ErrorT: BaseError](BaseSchema):
    status: int
    ok: bool = False
    trace_id: UUID
    error: ErrorT
