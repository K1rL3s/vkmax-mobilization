from datetime import datetime, timedelta

from zheka.core.services.files import FilesService
from zheka.infra.database.repos.files import FilesRepo
from zheka.infra.database.repos.idempotency import IdempotencyRepo

ATTACHMENT_TTL = timedelta(days=365)
ORPHAN_AGE = timedelta(days=1)
KEY_TTL = timedelta(days=1)


class RetentionService:
    __slots__ = ("_files", "_keys", "_repo")

    def __init__(
        self,
        files_repo: FilesRepo,
        files_service: FilesService,
        idempotency_repo: IdempotencyRepo,
    ) -> None:
        self._repo = files_repo
        self._files = files_service
        self._keys = idempotency_repo

    async def purge(self, now: datetime) -> int:
        referenced = await self._repo.referenced_names()
        removed = self._files.remove_orphans(referenced, now - ORPHAN_AGE)
        await self._repo.drop_request_attachments(now - ATTACHMENT_TTL)
        await self._repo.drop_reading_photos(now - ATTACHMENT_TTL)
        return removed

    async def purge_keys(self, now: datetime) -> int:
        return await self._keys.purge(now - KEY_TTL)
