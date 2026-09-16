import json
import logging
from datetime import UTC, datetime

from zheka.logger.context import COLUMNS


class JsonFormatter(logging.Formatter):
    def __init__(self, datefmt: str = "%Y-%m-%dT%H:%M:%S.%f") -> None:
        super().__init__(datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "time": self.formatTime(record, self.datefmt),
            "message": record.getMessage(),
            "logger_name": record.name,
            "lineno": record.lineno,
            "exception": (
                self.formatException(record.exc_info) if record.exc_info else None
            ),
            **{name: getattr(record, name, None) for name in COLUMNS},
            **getattr(record, "extra_data", {}),
        }
        return json.dumps(payload, ensure_ascii=False)

    def formatTime(  # noqa: N802
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        created = datetime.fromtimestamp(record.created, tz=UTC)
        if datefmt:
            return created.strftime(datefmt)
        return created.isoformat()
