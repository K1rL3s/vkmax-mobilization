from datetime import datetime, timedelta

from zheka.core.services.files import FilesService
from zheka.infra.database.repos.files import FilesRepo

PHOTO_TTL = timedelta(days=365)
ORPHAN_AGE = timedelta(days=1)


class RetentionService:
    __slots__ = ("_files", "_repo")

    def __init__(self, files_repo: FilesRepo, files_service: FilesService) -> None:
        self._repo = files_repo
        self._files = files_service

    async def purge(self, now: datetime) -> int:
        referenced = await self._repo.referenced_names()
        removed = self._files.remove_orphans(referenced, now - ORPHAN_AGE)
        await self._repo.drop_request_photos(now - PHOTO_TTL)
        await self._repo.drop_reading_photos(now - PHOTO_TTL)
        return removed
