from dishka import BaseScope, Provider, Scope, provide

from zheka.broker.publisher import TaskPublisher
from zheka.config import DeeplinksConfig, FilesConfig, MaxConfig
from zheka.core.services.access import AccessService
from zheka.core.services.admin_readings import AdminReadingsService
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.analytics import AnalyticsService
from zheka.core.services.announcements import AnnouncementsService
from zheka.core.services.charges import ChargesService
from zheka.core.services.chats import ChatsService
from zheka.core.services.demo import DemoService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.flats import FlatsService
from zheka.core.services.houses import HousesService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.meters import MetersService
from zheka.core.services.moderation import ModerationService
from zheka.core.services.notifications import NotificationsService
from zheka.core.services.orgs import OrgsService
from zheka.core.services.polls import PollsService
from zheka.core.services.profile import ProfileService
from zheka.core.services.readings import ReadingsService
from zheka.core.services.reception import ReceptionService
from zheka.core.services.reminders import RemindersService
from zheka.core.services.request_groups import GroupingService
from zheka.core.services.requests import RequestsService
from zheka.infra.database.repos.access import AccessRepo
from zheka.infra.database.repos.analytics import AnalyticsRepo
from zheka.infra.database.repos.announcements import AnnouncementsRepo
from zheka.infra.database.repos.charges import ChargesRepo
from zheka.infra.database.repos.chats import ChatsRepo
from zheka.infra.database.repos.events import EventsRepo
from zheka.infra.database.repos.flats import FlatsRepo
from zheka.infra.database.repos.houses import HousesRepo
from zheka.infra.database.repos.invites import InvitesRepo
from zheka.infra.database.repos.meters import MetersRepo
from zheka.infra.database.repos.notifications import NotificationsRepo
from zheka.infra.database.repos.orgs import OrgsRepo
from zheka.infra.database.repos.polls import PollsRepo
from zheka.infra.database.repos.reception import ReceptionRepo
from zheka.infra.database.repos.requests import RequestsRepo
from zheka.infra.database.repos.residents import ResidentsRepo
from zheka.infra.database.repos.users import UsersRepo


class ServicesProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST

    @provide
    def events_service(self, events_repo: EventsRepo) -> EventsService:
        return EventsService(events_repo)

    @provide
    def notifications_service(
        self,
        notifications_repo: NotificationsRepo,
        publisher: TaskPublisher,
        events_service: EventsService,
    ) -> NotificationsService:
        return NotificationsService(notifications_repo, publisher, events_service)

    @provide(scope=Scope.APP)
    def files_service(self, config: FilesConfig, max_config: MaxConfig) -> FilesService:
        return FilesService(config, max_config.token)

    @provide
    def houses_service(
        self,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
        users_repo: UsersRepo,
        flats_repo: FlatsRepo,
        events_service: EventsService,
    ) -> HousesService:
        return HousesService(
            houses_repo,
            residents_repo,
            orgs_repo,
            users_repo,
            flats_repo,
            events_service,
        )

    @provide
    def profile_service(
        self,
        users_repo: UsersRepo,
        residents_repo: ResidentsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        flats_repo: FlatsRepo,
    ) -> ProfileService:
        return ProfileService(
            users_repo,
            residents_repo,
            houses_repo,
            orgs_repo,
            flats_repo,
        )

    @provide
    def orgs_service(
        self,
        orgs_repo: OrgsRepo,
        invites_repo: InvitesRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
        deeplinks: DeeplinksConfig,
    ) -> OrgsService:
        return OrgsService(
            orgs_repo,
            invites_repo,
            houses_repo,
            users_repo,
            events_service,
            deeplinks,
        )

    @provide
    def moderation_service(
        self,
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        houses_repo: HousesRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> ModerationService:
        return ModerationService(
            residents_repo,
            users_repo,
            houses_repo,
            notifications_service,
            events_service,
        )

    @provide
    def flats_service(
        self,
        flats_repo: FlatsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        invites_repo: InvitesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> FlatsService:
        return FlatsService(
            flats_repo,
            houses_repo,
            residents_repo,
            invites_repo,
            users_repo,
            orgs_repo,
            notifications_service,
            events_service,
        )

    @provide
    def grouping_service(
        self,
        requests_repo: RequestsRepo,
        events_service: EventsService,
    ) -> GroupingService:
        return GroupingService(requests_repo, events_service)

    @provide
    def requests_service(
        self,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        files_service: FilesService,
        grouping_service: GroupingService,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> RequestsService:
        return RequestsService(
            requests_repo,
            houses_repo,
            residents_repo,
            users_repo,
            orgs_repo,
            files_service,
            grouping_service,
            notifications_service,
            events_service,
        )

    @provide
    def meter_access(
        self,
        meters_repo: MetersRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
    ) -> MeterAccess:
        return MeterAccess(meters_repo, houses_repo, residents_repo, orgs_repo)

    @provide
    def readings_service(
        self,
        meters_repo: MetersRepo,
        charges_repo: ChargesRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        access: MeterAccess,
        files_service: FilesService,
        events_service: EventsService,
    ) -> ReadingsService:
        return ReadingsService(
            meters_repo,
            charges_repo,
            houses_repo,
            orgs_repo,
            access,
            files_service,
            events_service,
        )

    @provide
    def meters_service(
        self,
        meters_repo: MetersRepo,
        access: MeterAccess,
    ) -> MetersService:
        return MetersService(meters_repo, access)

    @provide
    def charges_service(
        self,
        charges_repo: ChargesRepo,
        meters_repo: MetersRepo,
        houses_repo: HousesRepo,
        access: MeterAccess,
        readings_service: ReadingsService,
        requests_service: RequestsService,
        events_service: EventsService,
    ) -> ChargesService:
        return ChargesService(
            charges_repo,
            meters_repo,
            houses_repo,
            access,
            readings_service,
            requests_service,
            events_service,
        )

    @provide
    def polls_service(
        self,
        polls_repo: PollsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        orgs_repo: OrgsRepo,
        events_service: EventsService,
    ) -> PollsService:
        return PollsService(
            polls_repo,
            houses_repo,
            residents_repo,
            orgs_repo,
            events_service,
        )

    @provide
    def admin_readings_service(
        self,
        meters_repo: MetersRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
    ) -> AdminReadingsService:
        return AdminReadingsService(meters_repo, houses_repo, users_repo)

    @provide
    def admin_requests_service(
        self,
        requests_repo: RequestsRepo,
        houses_repo: HousesRepo,
        users_repo: UsersRepo,
        orgs_repo: OrgsRepo,
        grouping_service: GroupingService,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> AdminRequestsService:
        return AdminRequestsService(
            requests_repo,
            houses_repo,
            users_repo,
            orgs_repo,
            grouping_service,
            notifications_service,
            events_service,
        )

    @provide
    def announcements_service(
        self,
        announcements_repo: AnnouncementsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        chats_repo: ChatsRepo,
        orgs_repo: OrgsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> AnnouncementsService:
        return AnnouncementsService(
            announcements_repo,
            houses_repo,
            residents_repo,
            chats_repo,
            orgs_repo,
            notifications_service,
            events_service,
        )

    @provide
    def reception_service(
        self,
        reception_repo: ReceptionRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        residents_repo: ResidentsRepo,
        requests_repo: RequestsRepo,
        users_repo: UsersRepo,
        events_service: EventsService,
    ) -> ReceptionService:
        return ReceptionService(
            reception_repo,
            houses_repo,
            orgs_repo,
            residents_repo,
            requests_repo,
            users_repo,
            events_service,
        )

    @provide
    def access_service(
        self,
        access_repo: AccessRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        events_service: EventsService,
        notifications_service: NotificationsService,
    ) -> AccessService:
        return AccessService(
            access_repo,
            houses_repo,
            residents_repo,
            events_service,
            notifications_service,
        )

    @provide
    def chats_service(
        self,
        chats_repo: ChatsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        residents_repo: ResidentsRepo,
        notifications_service: NotificationsService,
        events_service: EventsService,
    ) -> ChatsService:
        return ChatsService(
            chats_repo,
            houses_repo,
            orgs_repo,
            residents_repo,
            notifications_service,
            events_service,
        )

    @provide
    def reminders_service(
        self,
        houses_repo: HousesRepo,
        meters_repo: MetersRepo,
        residents_repo: ResidentsRepo,
        polls_repo: PollsRepo,
        chats_repo: ChatsRepo,
        reception_repo: ReceptionRepo,
        events_repo: EventsRepo,
        events_service: EventsService,
        notifications_service: NotificationsService,
    ) -> RemindersService:
        return RemindersService(
            houses_repo,
            meters_repo,
            residents_repo,
            polls_repo,
            chats_repo,
            reception_repo,
            events_repo,
            events_service,
            notifications_service,
        )

    @provide
    def analytics_service(
        self,
        analytics_repo: AnalyticsRepo,
        houses_repo: HousesRepo,
        orgs_repo: OrgsRepo,
        reminders_service: RemindersService,
    ) -> AnalyticsService:
        return AnalyticsService(
            analytics_repo,
            houses_repo,
            orgs_repo,
            reminders_service,
        )

    @provide
    def demo_service(
        self,
        orgs_repo: OrgsRepo,
        houses_repo: HousesRepo,
        residents_repo: ResidentsRepo,
        meters_repo: MetersRepo,
        charges_repo: ChargesRepo,
        users_repo: UsersRepo,
    ) -> DemoService:
        return DemoService(
            orgs_repo,
            houses_repo,
            residents_repo,
            meters_repo,
            charges_repo,
            users_repo,
        )
