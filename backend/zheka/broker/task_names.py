from enum import StrEnum


class TaskName(StrEnum):
    # имя задачи - это контракт между тем, кто ставит, и тем, кто исполняет:
    # ставящий кикает по имени и сам модуль задач не импортирует
    AUTO_CLOSE_REVIEWED_REQUESTS = "auto_close_reviewed_requests"
    SEND_TO_USER = "send_to_user"
    BROADCAST_TO_USERS = "broadcast_to_users"
    BROADCAST_TO_CHATS = "broadcast_to_chats"
    CREATE_BOT_REQUEST = "create_bot_request"
