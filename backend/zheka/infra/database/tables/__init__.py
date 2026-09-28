from zheka.core import models
from zheka.infra.database.tables.access import (
    access_requests_table,
    access_slots_table,
    access_targets_table,
)
from zheka.infra.database.tables.announcements import announcements_table
from zheka.infra.database.tables.base import mapper_registry, metadata
from zheka.infra.database.tables.charges import charges_table, tariffs_table
from zheka.infra.database.tables.chats import (
    chat_cards_table,
    chat_pins_table,
    chats_table,
)
from zheka.infra.database.tables.events import events_table
from zheka.infra.database.tables.houses import flats_table, houses_table
from zheka.infra.database.tables.invites import flat_invites_table, org_invites_table
from zheka.infra.database.tables.meters import meters_table, readings_table
from zheka.infra.database.tables.organizations import (
    org_members_table,
    org_settings_table,
    organizations_table,
)
from zheka.infra.database.tables.polls import (
    poll_options_table,
    poll_votes_table,
    polls_table,
)
from zheka.infra.database.tables.reception import (
    appointments_table,
    reception_windows_table,
)
from zheka.infra.database.tables.requests import (
    request_groups_table,
    request_messages_table,
    request_photos_table,
    request_status_log_table,
    requests_table,
)
from zheka.infra.database.tables.residents import (
    chairman_handovers_table,
    demand_signals_table,
    flat_verification_requests_table,
    residents_table,
    verification_revocations_table,
)
from zheka.infra.database.tables.users import notification_settings_table, users_table

__all__ = ("mapper_registry", "metadata")

mapper_registry.map_imperatively(models.Organization, organizations_table)
mapper_registry.map_imperatively(models.OrgSettings, org_settings_table)
mapper_registry.map_imperatively(models.OrgMember, org_members_table)
mapper_registry.map_imperatively(models.AccessRequest, access_requests_table)
mapper_registry.map_imperatively(models.AccessSlot, access_slots_table)
mapper_registry.map_imperatively(models.AccessTarget, access_targets_table)
mapper_registry.map_imperatively(models.Announcement, announcements_table)
mapper_registry.map_imperatively(models.Tariff, tariffs_table)
mapper_registry.map_imperatively(models.Charge, charges_table)
mapper_registry.map_imperatively(models.Chat, chats_table)
mapper_registry.map_imperatively(models.ChatPin, chat_pins_table)
mapper_registry.map_imperatively(models.ChatCard, chat_cards_table)
mapper_registry.map_imperatively(models.Event, events_table)
mapper_registry.map_imperatively(models.House, houses_table)
mapper_registry.map_imperatively(models.Flat, flats_table)
mapper_registry.map_imperatively(models.OrgInvite, org_invites_table)
mapper_registry.map_imperatively(models.FlatInvite, flat_invites_table)
mapper_registry.map_imperatively(models.Meter, meters_table)
mapper_registry.map_imperatively(models.Reading, readings_table)
mapper_registry.map_imperatively(models.Poll, polls_table)
mapper_registry.map_imperatively(models.PollOption, poll_options_table)
mapper_registry.map_imperatively(models.PollVote, poll_votes_table)
mapper_registry.map_imperatively(models.ReceptionWindow, reception_windows_table)
mapper_registry.map_imperatively(models.Appointment, appointments_table)
mapper_registry.map_imperatively(models.Request, requests_table)
mapper_registry.map_imperatively(models.RequestGroup, request_groups_table)
mapper_registry.map_imperatively(models.RequestPhoto, request_photos_table)
mapper_registry.map_imperatively(models.RequestStatusLog, request_status_log_table)
mapper_registry.map_imperatively(models.RequestMessage, request_messages_table)
mapper_registry.map_imperatively(models.Resident, residents_table)
mapper_registry.map_imperatively(
    models.VerificationRequest,
    flat_verification_requests_table,
)
mapper_registry.map_imperatively(models.DemandSignal, demand_signals_table)
mapper_registry.map_imperatively(models.User, users_table)
mapper_registry.map_imperatively(
    models.NotificationSetting,
    notification_settings_table,
)
mapper_registry.map_imperatively(
    models.VerificationRevocation,
    verification_revocations_table,
)
mapper_registry.map_imperatively(models.ChairmanHandover, chairman_handovers_table)
