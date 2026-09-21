import json
import logging
from datetime import UTC, datetime

from zheka.logger.context import COLUMNS


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "time": datetime.fromtimestamp(record.created, tz=UTC).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            ),
            "message": record.getMessage(),
            "logger_name": record.name,
            "lineno": record.lineno,
            "exception": (
                self.formatException(record.exc_info) if record.exc_info else None
            ),
            **{name: getattr(record, name, None) for name in COLUMNS},
        }
        return json.dumps(payload, ensure_ascii=False)
