from typing import Self

from zheka.api.schemas.base import BaseSchema
from zheka.core.services.files import FilesService


class FileRef(BaseSchema):
    name: str
    url: str

    @classmethod
    def signed(cls, name: str, files_service: FilesService) -> Self:
        return cls(name=name, url=files_service.sign(name))


PHOTOS_DESCRIPTION = "Имена файлов из upload_file, не ссылки"
