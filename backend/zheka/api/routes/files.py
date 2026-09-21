from http import HTTPStatus

from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.files import FileRef
from zheka.core.errors import EntityNotFound
from zheka.core.services.files import FilesService

# роутер подключается без API_PREFIX: отдача файлов живет на своем пути nginx
router = APIRouter(tags=["Файлы"], route_class=DishkaRoute)


@router.post("/api/files", summary="Загрузить фото")
async def upload_file(
    current_account: RequireConsentDep,  # noqa: ARG001
    file: UploadFile,
    files_service: FromDishka[FilesService],
) -> FileRef:
    name = await files_service.save(file)
    return FileRef(name=name, url=files_service.sign(name))


@router.get(
    "/files/{name}",
    summary="Отдать файл с проверкой прав",
    response_class=FileResponse,
    responses={HTTPStatus.OK: {"content": {"application/octet-stream": {}}}},
)
async def download_file(
    name: str, exp: int, sig: str, files_service: FromDishka[FilesService]
) -> FileResponse:
    # без current_account: тег <img> не может отправить заголовок initData,
    # право на файл уже проверено при выпуске подписанной ссылки
    files_service.verify(name, exp, sig)
    path = files_service.path_of(name)
    if not path.is_file():
        raise EntityNotFound("Файл не найден")
    return FileResponse(path)
