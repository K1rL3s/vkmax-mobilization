from zheka.api.schemas.base import BaseSchema


class FileRef(BaseSchema):
    name: str
    url: str


PHOTOS_DESCRIPTION = "Имена файлов из upload_file, не ссылки"
