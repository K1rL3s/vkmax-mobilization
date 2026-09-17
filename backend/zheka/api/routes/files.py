from http import HTTPStatus

from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from zheka.api.dependencies import RequireConsentDep
from zheka.api.schemas.files import FileRef

# роутер подключается без API_PREFIX: отдача файлов живет на своем пути nginx
router = APIRouter(tags=["Файлы"], route_class=DishkaRoute)


@router.post("/api/files", summary="Загрузить фото")
async def upload_file(
    current_account: RequireConsentDep,
    file: UploadFile,
) -> FileRef:
    raise NotImplementedError("ещё не реализовано")


@router.get(
    "/files/{name}",
    summary="Отдать файл с проверкой прав",
    response_class=FileResponse,
    responses={HTTPStatus.OK: {"content": {"application/octet-stream": {}}}},
)
async def download_file(
    name: str,
    current_account: RequireConsentDep,
) -> FileResponse:
    raise NotImplementedError("ещё не реализовано")
