from zheka.core.models import (
    AccessRequest,
    AccessSlot,
    AccessTarget,
    Announcement,
    Appointment,
    Charge,
    Chat,
    DemandSignal,
    Event,
    Flat,
    FlatInvite,
    House,
    Meter,
    NotificationSetting,
    OrgInvite,
    OrgMember,
    OrgSettings,
    Organization,
    Poll,
    PollOption,
    PollVote,
    Reading,
    ReceptionWindow,
    Request,
    RequestGroup,
    RequestMessage,
    RequestPhoto,
    RequestStatusLog,
    Resident,
    Tariff,
    User,
    VerificationRequest,
)
from zheka.infra.database.tables.access import (
    access_requests_table,
    access_slots_table,
    access_targets_table,
)
from zheka.infra.database.tables.announcements import announcements_table
from zheka.infra.database.tables.base import mapper_registry, metadata
from zheka.infra.database.tables.charges import charges_table, tariffs_table
from zheka.infra.database.tables.chats import chats_table
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
    demand_signals_table,
    flat_verification_requests_table,
    residents_table,
)
from zheka.infra.database.tables.users import notification_settings_table, users_table

__all__ = ("mapper_registry", "metadata")

mapper_registry.map_imperatively(Organization, organizations_table)
mapper_registry.map_imperatively(OrgSettings, org_settings_table)
mapper_registry.map_imperatively(OrgMember, org_members_table)
mapper_registry.map_imperatively(AccessRequest, access_requests_table)
mapper_registry.map_imperatively(AccessSlot, access_slots_table)
mapper_registry.map_imperatively(AccessTarget, access_targets_table)
mapper_registry.map_imperatively(Announcement, announcements_table)
mapper_registry.map_imperatively(Tariff, tariffs_table)
mapper_registry.map_imperatively(Charge, charges_table)
mapper_registry.map_imperatively(Chat, chats_table)
mapper_registry.map_imperatively(Event, events_table)
mapper_registry.map_imperatively(House, houses_table)
mapper_registry.map_imperatively(Flat, flats_table)
mapper_registry.map_imperatively(OrgInvite, org_invites_table)
mapper_registry.map_imperatively(FlatInvite, flat_invites_table)
mapper_registry.map_imperatively(Meter, meters_table)
mapper_registry.map_imperatively(Reading, readings_table)
mapper_registry.map_imperatively(Poll, polls_table)
mapper_registry.map_imperatively(PollOption, poll_options_table)
mapper_registry.map_imperatively(PollVote, poll_votes_table)
mapper_registry.map_imperatively(ReceptionWindow, reception_windows_table)
mapper_registry.map_imperatively(Appointment, appointments_table)
mapper_registry.map_imperatively(Request, requests_table)
mapper_registry.map_imperatively(RequestGroup, request_groups_table)
mapper_registry.map_imperatively(RequestPhoto, request_photos_table)
mapper_registry.map_imperatively(RequestStatusLog, request_status_log_table)
mapper_registry.map_imperatively(RequestMessage, request_messages_table)
mapper_registry.map_imperatively(Resident, residents_table)
mapper_registry.map_imperatively(VerificationRequest, flat_verification_requests_table)
mapper_registry.map_imperatively(DemandSignal, demand_signals_table)
mapper_registry.map_imperatively(User, users_table)
mapper_registry.map_imperatively(NotificationSetting, notification_settings_table)
