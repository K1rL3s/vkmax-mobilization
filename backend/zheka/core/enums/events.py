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
    RESIDENT_BLOCKED = "resident_blocked"
    RESIDENT_UNBLOCKED = "resident_unblocked"

    LLM_SUGGESTED = "llm_suggested"
    LLM_ACCEPTED = "llm_accepted"

    REQUEST_JOINED = "request_joined"
    REQUEST_GROUP_FORMED = "request_group_formed"
    REQUEST_ASSIGNED = "request_assigned"
    EXECUTOR_STATUS_CHANGED = "executor_status_changed"
    REQUEST_REVIEWED = "request_reviewed"
    REQUEST_AUTO_CLOSED = "request_auto_closed"
    REQUEST_EXPORTED = "request_exported"

    FLAT_INVITE_CREATED = "flat_invite_created"
    FLAT_INVITE_ACTIVATED = "flat_invite_activated"

    APPOINTMENT_BOOKED = "appointment_booked"
    APPOINTMENT_REMINDER_SENT = "appointment_reminder_sent"

    ACCESS_REQUEST_SENT = "access_request_sent"
    ACCESS_SLOT_PICKED = "access_slot_picked"

    CHARGE_BREAKDOWN_OPENED = "charge_breakdown_opened"
    CHARGE_DISPUTED = "charge_disputed"


class EventSource(StrEnum):
    DIRECT = "direct"
    QR = "qr"
    CHAT = "chat"
    DEEPLINK = "deeplink"
    MINIAPP = "miniapp"
