import logging
from contextvars import ContextVar
from typing import Any

trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
update_id: ContextVar[str | None] = ContextVar("update_id", default=None)
max_user_id: ContextVar[int | None] = ContextVar("max_user_id", default=None)
task_id: ContextVar[str | None] = ContextVar("task_id", default=None)
task_name: ContextVar[str | None] = ContextVar("task_name", default=None)

COLUMNS: dict[str, ContextVar[Any]] = {
    column.name: column
    for column in (trace_id, update_id, max_user_id, task_id, task_name)
}


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for name, column in COLUMNS.items():
            setattr(record, name, column.get())
        return True
