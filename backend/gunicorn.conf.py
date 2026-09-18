import os

# BotMode.POLLING from zheka/config.py
POLLING_VALUE = "polling"


def _cores() -> int:
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


polling = os.environ.get("MAX_BOT_MODE", POLLING_VALUE).lower() == POLLING_VALUE

worker_class = "asgi"

bind = "{}:{}".format(
    os.environ.get("API_HOST", "0.0.0.0"),  # noqa: S104 # nosec B104
    os.environ.get("API_PORT", "7001"),
)

workers = 1 if polling else _cores()
