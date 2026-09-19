from enum import StrEnum

from environs import Env
from sqlalchemy import URL

from zheka.base import ZhekaType


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


class DbConfig(ZhekaType):
    host: str
    port: int
    user: str
    password: str
    name: str
    driver: str = "postgresql+psycopg"

    @property
    def url(self) -> URL:
        return URL.create(
            drivername=self.driver,
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


class Config(ZhekaType):
    log: LogConfig
    api: ApiConfig
    db: DbConfig
    redis: RedisConfig
    max: MaxConfig
    files: FilesConfig
    deeplinks: DeeplinksConfig


def load_config(env_path: str | None = None) -> Config:
    env = Env()
    env.read_env(env_path, recurse=True)

    config = Config(
        log=_load_log(env),
        api=_load_api(env),
        db=_load_db(env),
        redis=_load_redis(env),
        max=_load_max(env),
        files=_load_files(env),
        deeplinks=_load_deeplinks(env),
    )
    if config.max.mode is BotMode.WEBHOOK and not config.max.webhook_url:
        raise ValueError("MAX_WEBHOOK_URL обязателен при MAX_BOT_MODE=webhook")
    return config


def _load_log(env: Env) -> LogConfig:
    return LogConfig(
        level=env.str("LOG_LEVEL", "INFO").upper(),
        format=LogFormat(env.str("LOG_FORMAT", LogFormat.JSON).upper()),
    )


def _load_api(env: Env) -> ApiConfig:
    # адрес, порт и число воркеров читает gunicorn из своих флагов, не приложение
    with env.prefixed("API_"):
        return ApiConfig(cors=tuple(env.list("CORS", [])))


def _load_db(env: Env) -> DbConfig:
    with env.prefixed("POSTGRES_"):
        return DbConfig(
            host=env.str("HOST"),
            port=env.int("PORT", 5432),
            user=env.str("USER"),
            password=env.str("PASSWORD"),
            name=env.str("DB"),
        )


def _load_redis(env: Env) -> RedisConfig:
    with env.prefixed("REDIS_"):
        return RedisConfig(
            host=env.str("HOST"),
            port=env.int("PORT", 6379),
            password=env.str("PASSWORD", None),
            db=env.int("DB", 0),
        )


def _load_max(env: Env) -> MaxConfig:
    with env.prefixed("MAX_"):
        return MaxConfig(
            token=env.str("TOKEN"),
            mode=BotMode(env.str("BOT_MODE", BotMode.POLLING).lower()),
            webhook_url=env.str("WEBHOOK_URL", None),
            secret_token=env.str("SECRET_TOKEN", None),
        )


def _load_files(env: Env) -> FilesConfig:
    with env.prefixed("FILES_"):
        return FilesConfig(
            dir=env.str("DIR", "/data/files"),
            max_size_mb=env.int("MAX_SIZE_MB", 10),
        )


def _load_deeplinks(env: Env) -> DeeplinksConfig:
    with env.prefixed("DEEPLINK_"):
        # у кода регистрации нет значения по умолчанию: пустой секрет, который
        # молча работает, хуже ошибки на старте
        org_register = env.str("ORG_REGISTER")
    # сравнение с кодом идет через secrets.compare_digest, а он на не-ASCII
    # бросает TypeError - то есть 500 на первом же запросе вместо ошибки старта
    if not org_register.isascii():
        raise ValueError("DEEPLINK_ORG_REGISTER должен состоять только из ASCII")
    return DeeplinksConfig(org_register=org_register)
