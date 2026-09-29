from enum import StrEnum


class AnnouncementChannel(StrEnum):
    CHAT = "chat"
    DIRECT = "direct"


class NoticeStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    MUTED = "muted"
    BOT_STOPPED = "bot_stopped"
