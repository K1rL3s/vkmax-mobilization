from enum import StrEnum


class EventType(StrEnum):
    BOT_START = "bot_start"
    BOT_MUTED = "bot_muted"
    BOT_UNMUTED = "bot_unmuted"
    BOT_STOPPED = "bot_stopped"

    MINIAPP_OPEN = "miniapp_open"

    HOUSE_SEARCH = "house_search"
    HOUSE_LINKED = "house_linked"
    HOUSE_LEFT = "house_left"
    DEMAND_SIGNAL = "demand_signal"

    FLAT_VERIFICATION_REQUESTED = "flat_verification_requested"
    FLAT_VERIFIED = "flat_verified"
    FLAT_VERIFICATION_REVOKED = "flat_verification_revoked"

    REQUEST_CREATED = "request_created"
    REQUEST_STATUS_CHANGED = "request_status_changed"
    REQUEST_RATED = "request_rated"

    READING_SUBMITTED = "reading_submitted"
    READING_REMINDER_SENT = "reading_reminder_sent"

    POLL_CREATED = "poll_created"
    POLL_VOTED = "poll_voted"

    ANNOUNCEMENT_SENT = "announcement_sent"
    ANNOUNCEMENT_CLICK = "announcement_click"

    CHAT_BOUND = "chat_bound"
    CHAT_ADMIN_GRANTED = "chat_admin_granted"

    NOTIFICATION_SETTINGS_CHANGED = "notification_settings_changed"

    ORG_REGISTERED = "org_registered"
    STAFF_INVITED = "staff_invited"

    LLM_SUGGESTED = "llm_suggested"
    LLM_ACCEPTED = "llm_accepted"
