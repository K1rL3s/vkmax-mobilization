from zheka.bot.handlers.chats import chat_binding_dialog, chats_router
from zheka.bot.handlers.commands import commands_router, deeplinks_router
from zheka.bot.handlers.consent import consent_dialog
from zheka.bot.handlers.errors import error_router
from zheka.bot.handlers.executor import executor_dialog
from zheka.bot.handlers.fallback import router as fallback_router
from zheka.bot.handlers.lifecycle import router as lifecycle_router
from zheka.bot.handlers.menu import menu_dialog
from zheka.bot.handlers.onboarding import onboarding_dialog
from zheka.bot.handlers.requests import request_dialog
from zheka.bot.handlers.review import review_dialog

__all__ = (
    "chat_binding_dialog",
    "chats_router",
    "commands_router",
    "consent_dialog",
    "deeplinks_router",
    "error_router",
    "executor_dialog",
    "fallback_router",
    "lifecycle_router",
    "menu_dialog",
    "onboarding_dialog",
    "request_dialog",
    "review_dialog",
)
