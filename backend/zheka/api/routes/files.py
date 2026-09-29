from http import HTTPStatus

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from zheka.api.dependencies import CurrentOrgDep, RequireConsentDep
from zheka.api.schemas.files import FileRef
from zheka.core.errors import EntityNotFound, TooManyRequests
from zheka.core.services.files import FilesService
from zheka.infra.quota import UploadQuota

router = APIRouter(tags=["Файлы"], route_class=DishkaRoute)


@router.post("/api/files", summary="Загрузить фото или видео")
async def upload_file(
    current_account: RequireConsentDep,
    file: UploadFile,
    files_service: FromDishka[FilesService],
    quota: FromDishka[UploadQuota],
) -> FileRef:
    if not quota.take(current_account.user_id):
        raise TooManyRequests
    name = await files_service.save(file)
    return FileRef.signed(name, files_service)


@router.get(
    "/files/{name}",
    summary="Отдать файл с проверкой прав",
    response_class=FileResponse,
    responses={HTTPStatus.OK: {"content": {"application/octet-stream": {}}}},
)
async def download_file(
    name: str,
    exp: int,
    sig: str,
    files_service: FromDishka[FilesService],
) -> FileResponse:
    files_service.verify(name, exp, sig)
    path = files_service.path_of(name)
    if not path.is_file():
        raise EntityNotFound("Файл не найден")
    return FileResponse(path)


@router.post(
    "/api/admin/files",
    summary="Загрузить документ PDF",
    description="Только сотрудникам УК: приказ или график к объявлению",
)
async def upload_document(
    current_org: CurrentOrgDep,
    file: UploadFile,
    files_service: FromDishka[FilesService],
    quota: FromDishka[UploadQuota],
) -> FileRef:
    if not quota.take(current_org.user_id):
        raise TooManyRequests
    name = await files_service.save_document(file)
    return FileRef.signed(name, files_service)
