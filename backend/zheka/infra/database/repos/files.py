from datetime import datetime

from sqlalchemy import delete, func, select, union, update

from zheka.infra.database.repos.base import BaseAlchemyRepo
from zheka.infra.database.tables.charges import tariffs_table
from zheka.infra.database.tables.houses import houses_table
from zheka.infra.database.tables.meters import readings_table
from zheka.infra.database.tables.requests import request_photos_table, requests_table


class FilesRepo(BaseAlchemyRepo):
    async def referenced_names(self) -> set[str]:
        stmt = union(
            select(request_photos_table.c.path),
            select(func.jsonb_array_elements_text(readings_table.c.photo_paths)),
            select(func.jsonb_array_elements_text(houses_table.c.documents)),
            select(tariffs_table.c.document_url).where(
                tariffs_table.c.document_url.is_not(None),
            ),
        )
        result = await self._session.execute(stmt)
        return set(result.scalars().all())

    async def drop_request_photos(self, done_before: datetime) -> None:
        closed = select(requests_table.c.id).where(
            requests_table.c.done_at < done_before,
        )
        stmt = delete(request_photos_table).where(
            request_photos_table.c.request_id.in_(closed),
        )
        await self._session.execute(stmt)

    async def drop_reading_photos(self, submitted_before: datetime) -> None:
        stmt = (
            update(readings_table)
            .where(
                readings_table.c.submitted_at < submitted_before,
                func.jsonb_array_length(readings_table.c.photo_paths) > 0,
            )
            .values(photo_paths=[])
        )
        await self._session.execute(stmt)
