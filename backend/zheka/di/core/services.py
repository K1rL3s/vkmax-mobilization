from dishka import BaseScope, Provider, Scope, provide, provide_all

from zheka.config import FilesConfig, MaxConfig
from zheka.core.services.access import AccessService
from zheka.core.services.admin_map import AdminMapService
from zheka.core.services.admin_readings import AdminReadingsService
from zheka.core.services.admin_requests import AdminRequestsService
from zheka.core.services.analytics import AnalyticsService
from zheka.core.services.announcements import AnnouncementsService
from zheka.core.services.category_executors import CategoryExecutorsService
from zheka.core.services.charges import ChargesService
from zheka.core.services.chat_cards import ChatCardsService
from zheka.core.services.chats import ChatsService
from zheka.core.services.demo import DemoService
from zheka.core.services.events import EventsService
from zheka.core.services.files import FilesService
from zheka.core.services.flats import FlatsService
from zheka.core.services.house_point import HousePointService
from zheka.core.services.houses import HousesService
from zheka.core.services.map import MapService
from zheka.core.services.meter_access import MeterAccess
from zheka.core.services.meter_photo import MeterPhotoService
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
from zheka.core.services.retention import RetentionService
from zheka.infra.quota import HouseAddQuota, HouseLookupQuota, UploadQuota


class ServicesProvider(Provider):
    scope: BaseScope | None = Scope.REQUEST

    services = provide_all(
        EventsService,
        NotificationsService,
        HousesService,
        ProfileService,
        OrgsService,
        ModerationService,
        FlatsService,
        GroupingService,
        CategoryExecutorsService,
        RequestsService,
        MeterAccess,
        ReadingsService,
        MetersService,
        ChargesService,
        PollsService,
        AdminReadingsService,
        AdminRequestsService,
        AnnouncementsService,
        ReceptionService,
        AccessService,
        ChatsService,
        ChatCardsService,
        MeterPhotoService,
        RemindersService,
        AnalyticsService,
        DemoService,
        RetentionService,
        MapService,
        HousePointService,
        AdminMapService,
    )
    upload_quota = provide(UploadQuota, scope=Scope.APP)
    house_add_quota = provide(HouseAddQuota, scope=Scope.APP)
    house_lookup_quota = provide(HouseLookupQuota, scope=Scope.APP)

    @provide(scope=Scope.APP)
    def files_service(self, config: FilesConfig, max_config: MaxConfig) -> FilesService:
        return FilesService(config, max_config.token)
