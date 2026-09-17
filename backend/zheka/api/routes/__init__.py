from zheka.api.routes.admin import (
    admin_analytics_router,
    admin_announcements_router,
    admin_houses_router,
    admin_meters_router,
    admin_orgs_router,
    admin_polls_router,
    admin_reception_router,
    admin_requests_router,
)
from zheka.api.routes.announcements import router as announcements_router
from zheka.api.routes.charges import router as charges_router
from zheka.api.routes.demo import router as demo_router
from zheka.api.routes.files import router as files_router
from zheka.api.routes.flats import router as flats_router
from zheka.api.routes.healthcheck import router as healthcheck_router
from zheka.api.routes.houses import router as houses_router
from zheka.api.routes.me import router as me_router
from zheka.api.routes.meters import router as meters_router
from zheka.api.routes.orgs import router as orgs_router
from zheka.api.routes.polls import router as polls_router
from zheka.api.routes.reception import router as reception_router
from zheka.api.routes.requests import router as requests_router

__all__ = (
    "admin_analytics_router",
    "admin_announcements_router",
    "admin_houses_router",
    "admin_meters_router",
    "admin_orgs_router",
    "admin_polls_router",
    "admin_reception_router",
    "admin_requests_router",
    "announcements_router",
    "charges_router",
    "demo_router",
    "files_router",
    "flats_router",
    "healthcheck_router",
    "houses_router",
    "me_router",
    "meters_router",
    "orgs_router",
    "polls_router",
    "reception_router",
    "requests_router",
)
