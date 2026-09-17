from zheka.api.routes.admin.analytics import router as admin_analytics_router
from zheka.api.routes.admin.announcements import router as admin_announcements_router
from zheka.api.routes.admin.houses import router as admin_houses_router
from zheka.api.routes.admin.meters import router as admin_meters_router
from zheka.api.routes.admin.orgs import router as admin_orgs_router
from zheka.api.routes.admin.polls import router as admin_polls_router
from zheka.api.routes.admin.reception import router as admin_reception_router
from zheka.api.routes.admin.requests import router as admin_requests_router

__all__ = (
    "admin_analytics_router",
    "admin_announcements_router",
    "admin_houses_router",
    "admin_meters_router",
    "admin_orgs_router",
    "admin_polls_router",
    "admin_reception_router",
    "admin_requests_router",
)
