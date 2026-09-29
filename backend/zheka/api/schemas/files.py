from typing import Self

from zheka.api.schemas.base import BaseSchema
from zheka.core.services.files import FilesService


class FileRef(BaseSchema):
    name: str
    url: str
    is_video: bool

    @classmethod
    def signed(cls, name: str, files_service: FilesService) -> Self:
        return cls(
            name=name,
            url=files_service.sign(name),
            is_video=files_service.is_video(name),
        )


FILES_DESCRIPTION = "Имена файлов из upload_file, не ссылки"
