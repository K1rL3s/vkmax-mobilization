from collections.abc import Sequence

from zheka.core.errors import EntityNotFound, InvalidRequest
from zheka.core.ids import HouseDocumentId, HouseId, OrgId
from zheka.core.models import HouseDocument
from zheka.core.services.announcements import DOCUMENT_NOT_FOUND
from zheka.core.services.files import PDF_SUFFIX, FilesService
from zheka.infra.database.repos.houses import HousesRepo

HOUSE_NOT_FOUND = "Дом не найден"
EMPTY_TITLE = "Укажите название документа"


class HouseDocumentsService:
    __slots__ = ("_files", "_houses")

    def __init__(self, houses_repo: HousesRepo, files_service: FilesService) -> None:
        self._houses = houses_repo
        self._files = files_service

    async def list(self, org_id: OrgId, house_id: HouseId) -> Sequence[HouseDocument]:
        await self._org_house(org_id, house_id)
        return await self._houses.list_documents(house_id)

    async def add(
        self,
        org_id: OrgId,
        house_id: HouseId,
        name: str,
        title: str,
    ) -> HouseDocument:
        await self._org_house(org_id, house_id)
        if not title.strip():
            raise InvalidRequest(EMPTY_TITLE)
        if not name.endswith(PDF_SUFFIX) or not self._files.path_of(name).is_file():
            raise EntityNotFound(DOCUMENT_NOT_FOUND)
        return await self._houses.add_document(
            HouseDocument(house_id=house_id, name=name, title=title.strip()),
        )

    async def delete(
        self,
        org_id: OrgId,
        house_id: HouseId,
        document_id: HouseDocumentId,
    ) -> None:
        await self._org_house(org_id, house_id)
        if not await self._houses.delete_document(house_id, document_id):
            raise EntityNotFound(DOCUMENT_NOT_FOUND)

    async def _org_house(self, org_id: OrgId, house_id: HouseId) -> None:
        if await self._houses.get_for_org(house_id, org_id) is None:
            raise EntityNotFound(HOUSE_NOT_FOUND)
