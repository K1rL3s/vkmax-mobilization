from enum import StrEnum


class TaskName(StrEnum):
    # имя задачи - это контракт между тем, кто ставит, и тем, кто исполняет:
    # ставящий кикает по имени и сам модуль задач не импортирует
    AUTO_CLOSE_REVIEWED_REQUESTS = "auto_close_reviewed_requests"
    SEND_TO_USER = "send_to_user"
    BROADCAST_TO_USERS = "broadcast_to_users"
    BROADCAST_TO_CHATS = "broadcast_to_chats"
    CREATE_BOT_REQUEST = "create_bot_request"
    SEND_EXECUTOR_CARD = "send_executor_card"
    SEND_REVIEW_CARD = "send_review_card"
    ATTACH_RESULT_PHOTO = "attach_result_photo"
    ON_BOT_ADDED = "on_bot_added"
    WELCOME_CHAT = "welcome_chat"
    REMIND_READINGS = "remind_readings"
    REMIND_POLLS = "remind_polls"
    CLOSE_EXPIRED_POLLS = "close_expired_polls"
    WARN_VERIFICATION = "warn_verification"
    REMIND_APPOINTMENTS = "remind_appointments"
    BROADCAST_ACCESS_REQUEST = "broadcast_access_request"
    SEED_DEMO = "seed_demo"
