"""add foreign key and lookup indexes

Revision ID: fba27f8b4756
Revises: 4c7e1a9b3d62
Create Date: 2026-10-24 14:04:18.086528

"""

from collections.abc import Sequence

from alembic import op

revision: str = "fba27f8b4756"
down_revision: str | None = "4c7e1a9b3d62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_access_requests_created_by"),
        "access_requests",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_requests_house_id"),
        "access_requests",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_requests_org_id"),
        "access_requests",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_slots_access_request_id"),
        "access_slots",
        ["access_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_targets_access_request_id"),
        "access_targets",
        ["access_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_targets_flat_id"),
        "access_targets",
        ["flat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_access_targets_slot_id"),
        "access_targets",
        ["slot_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_announcements_created_by"),
        "announcements",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_announcements_org_id"),
        "announcements",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_announcements_poll_id"),
        "announcements",
        ["poll_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_house_id"),
        "appointments",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_org_id"),
        "appointments",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_request_id"),
        "appointments",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_appointments_user_id"),
        "appointments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chairman_handovers_accepted_by"),
        "chairman_handovers",
        ["accepted_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chairman_handovers_created_by"),
        "chairman_handovers",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_members_user_id"),
        "chat_members",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_pins_pinned_by"),
        "chat_pins",
        ["pinned_by"],
        unique=False,
    )
    op.create_index(op.f("ix_chats_bound_by"), "chats", ["bound_by"], unique=False)
    op.create_index(op.f("ix_chats_house_id"), "chats", ["house_id"], unique=False)
    op.create_index(
        op.f("ix_council_proposals_poll_id"),
        "council_proposals",
        ["poll_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_demand_signals_user_id"),
        "demand_signals",
        ["user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_events_user_id"), "events", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_flat_invites_created_by"),
        "flat_invites",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flat_invites_flat_id"),
        "flat_invites",
        ["flat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flat_verification_requests_decided_by"),
        "flat_verification_requests",
        ["decided_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flat_verification_requests_flat_id"),
        "flat_verification_requests",
        ["flat_id"],
        unique=False,
    )
    op.create_index(op.f("ix_houses_lat"), "houses", ["lat", "lon"], unique=False)
    op.create_index(op.f("ix_houses_org_id"), "houses", ["org_id"], unique=False)
    op.create_index(
        op.f("ix_notice_deliveries_flat_id"),
        "notice_deliveries",
        ["flat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notice_deliveries_house_id"),
        "notice_deliveries",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notice_deliveries_user_id"),
        "notice_deliveries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_org_category_executors_executor_user_id"),
        "org_category_executors",
        ["executor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_org_invites_created_by"),
        "org_invites",
        ["created_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_org_invites_org_id"),
        "org_invites",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_org_members_user_id"),
        "org_members",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_poll_options_poll_id"),
        "poll_options",
        ["poll_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_poll_votes_flat_id"),
        "poll_votes",
        ["flat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_poll_votes_option_id"),
        "poll_votes",
        ["option_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_poll_votes_resident_id"),
        "poll_votes",
        ["resident_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_poll_votes_user_id"),
        "poll_votes",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_polls_created_by_user_id"),
        "polls",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_polls_house_id"), "polls", ["house_id"], unique=False)
    op.create_index(op.f("ix_polls_org_id"), "polls", ["org_id"], unique=False)
    op.create_index(
        op.f("ix_readings_submitted_by"),
        "readings",
        ["submitted_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reception_windows_org_id"),
        "reception_windows",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_groups_house_id"),
        "request_groups",
        ["house_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_messages_author_user_id"),
        "request_messages",
        ["author_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_messages_request_id"),
        "request_messages",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_photos_request_id"),
        "request_photos",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_photos_uploaded_by"),
        "request_photos",
        ["uploaded_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_status_log_by_user_id"),
        "request_status_log",
        ["by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_request_status_log_request_id"),
        "request_status_log",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requests_author_user_id"),
        "requests",
        ["author_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_requests_flat_id"), "requests", ["flat_id"], unique=False)
    op.create_index(
        op.f("ix_requests_parent_request_id"),
        "requests",
        ["parent_request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requests_status"),
        "requests",
        ["status", "deadline_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_residents_flat_id"),
        "residents",
        ["flat_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_residents_verified_by"),
        "residents",
        ["verified_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenancies_ended_by"),
        "tenancies",
        ["ended_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenancies_user_id"),
        "tenancies",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_verification_revocations_flat_id"),
        "verification_revocations",
        ["flat_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_verification_revocations_flat_id"),
        table_name="verification_revocations",
    )
    op.drop_index(op.f("ix_tenancies_user_id"), table_name="tenancies")
    op.drop_index(op.f("ix_tenancies_ended_by"), table_name="tenancies")
    op.drop_index(op.f("ix_residents_verified_by"), table_name="residents")
    op.drop_index(op.f("ix_residents_flat_id"), table_name="residents")
    op.drop_index(op.f("ix_requests_status"), table_name="requests")
    op.drop_index(op.f("ix_requests_parent_request_id"), table_name="requests")
    op.drop_index(op.f("ix_requests_flat_id"), table_name="requests")
    op.drop_index(op.f("ix_requests_author_user_id"), table_name="requests")
    op.drop_index(
        op.f("ix_request_status_log_request_id"),
        table_name="request_status_log",
    )
    op.drop_index(
        op.f("ix_request_status_log_by_user_id"),
        table_name="request_status_log",
    )
    op.drop_index(op.f("ix_request_photos_uploaded_by"), table_name="request_photos")
    op.drop_index(op.f("ix_request_photos_request_id"), table_name="request_photos")
    op.drop_index(op.f("ix_request_messages_request_id"), table_name="request_messages")
    op.drop_index(
        op.f("ix_request_messages_author_user_id"),
        table_name="request_messages",
    )
    op.drop_index(op.f("ix_request_groups_house_id"), table_name="request_groups")
    op.drop_index(op.f("ix_reception_windows_org_id"), table_name="reception_windows")
    op.drop_index(op.f("ix_readings_submitted_by"), table_name="readings")
    op.drop_index(op.f("ix_polls_org_id"), table_name="polls")
    op.drop_index(op.f("ix_polls_house_id"), table_name="polls")
    op.drop_index(op.f("ix_polls_created_by_user_id"), table_name="polls")
    op.drop_index(op.f("ix_poll_votes_user_id"), table_name="poll_votes")
    op.drop_index(op.f("ix_poll_votes_resident_id"), table_name="poll_votes")
    op.drop_index(op.f("ix_poll_votes_option_id"), table_name="poll_votes")
    op.drop_index(op.f("ix_poll_votes_flat_id"), table_name="poll_votes")
    op.drop_index(op.f("ix_poll_options_poll_id"), table_name="poll_options")
    op.drop_index(op.f("ix_org_members_user_id"), table_name="org_members")
    op.drop_index(op.f("ix_org_invites_org_id"), table_name="org_invites")
    op.drop_index(op.f("ix_org_invites_created_by"), table_name="org_invites")
    op.drop_index(
        op.f("ix_org_category_executors_executor_user_id"),
        table_name="org_category_executors",
    )
    op.drop_index(op.f("ix_notice_deliveries_user_id"), table_name="notice_deliveries")
    op.drop_index(op.f("ix_notice_deliveries_house_id"), table_name="notice_deliveries")
    op.drop_index(op.f("ix_notice_deliveries_flat_id"), table_name="notice_deliveries")
    op.drop_index(op.f("ix_houses_org_id"), table_name="houses")
    op.drop_index(op.f("ix_houses_lat"), table_name="houses")
    op.drop_index(
        op.f("ix_flat_verification_requests_flat_id"),
        table_name="flat_verification_requests",
    )
    op.drop_index(
        op.f("ix_flat_verification_requests_decided_by"),
        table_name="flat_verification_requests",
    )
    op.drop_index(op.f("ix_flat_invites_flat_id"), table_name="flat_invites")
    op.drop_index(op.f("ix_flat_invites_created_by"), table_name="flat_invites")
    op.drop_index(op.f("ix_events_user_id"), table_name="events")
    op.drop_index(op.f("ix_demand_signals_user_id"), table_name="demand_signals")
    op.drop_index(op.f("ix_council_proposals_poll_id"), table_name="council_proposals")
    op.drop_index(op.f("ix_chats_house_id"), table_name="chats")
    op.drop_index(op.f("ix_chats_bound_by"), table_name="chats")
    op.drop_index(op.f("ix_chat_pins_pinned_by"), table_name="chat_pins")
    op.drop_index(op.f("ix_chat_members_user_id"), table_name="chat_members")
    op.drop_index(
        op.f("ix_chairman_handovers_created_by"),
        table_name="chairman_handovers",
    )
    op.drop_index(
        op.f("ix_chairman_handovers_accepted_by"),
        table_name="chairman_handovers",
    )
    op.drop_index(op.f("ix_appointments_user_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_request_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_org_id"), table_name="appointments")
    op.drop_index(op.f("ix_appointments_house_id"), table_name="appointments")
    op.drop_index(op.f("ix_announcements_poll_id"), table_name="announcements")
    op.drop_index(op.f("ix_announcements_org_id"), table_name="announcements")
    op.drop_index(op.f("ix_announcements_created_by"), table_name="announcements")
    op.drop_index(op.f("ix_access_targets_slot_id"), table_name="access_targets")
    op.drop_index(op.f("ix_access_targets_flat_id"), table_name="access_targets")
    op.drop_index(
        op.f("ix_access_targets_access_request_id"),
        table_name="access_targets",
    )
    op.drop_index(op.f("ix_access_slots_access_request_id"), table_name="access_slots")
    op.drop_index(op.f("ix_access_requests_org_id"), table_name="access_requests")
    op.drop_index(op.f("ix_access_requests_house_id"), table_name="access_requests")
    op.drop_index(op.f("ix_access_requests_created_by"), table_name="access_requests")
