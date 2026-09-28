from zheka.infra.quota import Quota

QUOTA_CALLS = 60
QUOTA_WINDOW_SECONDS = 3600.0


class YandexQuota(Quota):
    __slots__ = ()

    calls = QUOTA_CALLS
    window_seconds = QUOTA_WINDOW_SECONDS
