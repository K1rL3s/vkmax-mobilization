import re
from enum import StrEnum

from environs import Env
from sqlalchemy import URL

from zheka.base import ZhekaType

YANDEX_DEFAULT_MODEL = "yandexgpt-5-lite"
REGISTER_CODE = re.compile(r"[A-Za-z0-9_-]{1,64}")


class BotMode(StrEnum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class LogFormat(StrEnum):
    JSON = "JSON"
    PLAIN = "PLAIN"


class LogConfig(ZhekaType):
    level: str
    format: LogFormat


class ApiConfig(ZhekaType):
    cors: tuple[str, ...]
    test_token: str | None = None


class DbConfig(ZhekaType):
    host: str
    port: int
    user: str
    password: str
    name: str

    @property
    def url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
        )


class RedisConfig(ZhekaType):
    host: str
    port: int
    password: str | None
    db: int

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class MaxConfig(ZhekaType):
    token: str
    mode: BotMode
    webhook_url: str | None
    secret_token: str | None


class FilesConfig(ZhekaType):
    dir: str
    max_size_mb: int


class DeeplinksConfig(ZhekaType):
    org_register: str


class YandexConfig(ZhekaType):
    api_key: str | None
    folder_id: str | None
    model: str = YANDEX_DEFAULT_MODEL


class Config(ZhekaType):
    log: LogConfig
    api: ApiConfig
    db: DbConfig
    redis: RedisConfig
    max: MaxConfig
    files: FilesConfig
    deeplinks: DeeplinksConfig
    yandex: YandexConfig


def load_config(env_path: str | None = None) -> Config:
    env = Env()
    env.read_env(env_path, recurse=True)

    org_register = env.str("DEEPLINK_ORG_REGISTER")
    if not REGISTER_CODE.fullmatch(org_register):
        raise ValueError(
            "DEEPLINK_ORG_REGISTER: от 1 до 64 символов из латиницы, цифр, _ и -",
        )

    config = Config(
        log=LogConfig(
            level=env.str("LOG_LEVEL", "INFO").upper(),
            format=LogFormat(env.str("LOG_FORMAT", LogFormat.JSON).upper()),
        ),
        api=ApiConfig(
            cors=tuple(env.list("API_CORS", [])),
            test_token=env.str("API_TEST_TOKEN", "") or None,
        ),
        db=DbConfig(
            host=env.str("POSTGRES_HOST"),
            port=env.int("POSTGRES_PORT", 5432),
            user=env.str("POSTGRES_USER"),
            password=env.str("POSTGRES_PASSWORD"),
            name=env.str("POSTGRES_DB"),
        ),
        redis=RedisConfig(
            host=env.str("REDIS_HOST"),
            port=env.int("REDIS_PORT", 6379),
            password=env.str("REDIS_PASSWORD", None),
            db=env.int("REDIS_DB", 0),
        ),
        max=MaxConfig(
            token=env.str("MAX_TOKEN"),
            mode=BotMode(env.str("MAX_BOT_MODE", BotMode.POLLING).lower()),
            webhook_url=env.str("MAX_WEBHOOK_URL", None),
            secret_token=env.str("MAX_SECRET_TOKEN", None),
        ),
        files=FilesConfig(
            dir=env.str("FILES_DIR", "/data/files"),
            max_size_mb=env.int("FILES_MAX_SIZE_MB", 10),
        ),
        deeplinks=DeeplinksConfig(org_register=org_register),
        yandex=YandexConfig(
            api_key=env.str("YANDEX_API_KEY", None),
            folder_id=env.str("YANDEX_FOLDER_ID", None),
            model=env.str("YANDEX_MODEL", YANDEX_DEFAULT_MODEL),
        ),
    )
    if config.max.mode is BotMode.WEBHOOK and not config.max.webhook_url:
        raise ValueError("MAX_WEBHOOK_URL обязателен при MAX_BOT_MODE=webhook")
    return config
