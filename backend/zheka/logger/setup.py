import logging

from zheka.config import LogConfig, LogFormat
from zheka.logger.context import ContextFilter
from zheka.logger.formatter import JsonFormatter


def setup_logger(config: LogConfig) -> None:
    if config.format is LogFormat.JSON:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)8s] %(message)s (%(name)s:%(lineno)s)",
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(config.level)

    for name in (
        "aiohttp.access",
        "asyncio",
        "sqlalchemy.engine.Engine",
        "taskiq.receiver.receiver",
        "unihttp.http.request",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
