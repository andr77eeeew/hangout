from aiogram import Router
from bot.handlers.activities import router as activities_router
from bot.handlers.link import router as link_router
from bot.handlers.membership import router as membership_router
from bot.handlers.moderation import router as moderation_router
from bot.handlers.notifications import router as notifications_router
from bot.handlers.start import router as start_router
from bot.handlers.tags import router as tags_router


def get_handlers_router() -> Router:
    parent_router = Router()
    parent_router.include_router(start_router)
    parent_router.include_router(link_router)
    parent_router.include_router(notifications_router)
    parent_router.include_router(activities_router)
    parent_router.include_router(membership_router)
    parent_router.include_router(tags_router)
    parent_router.include_router(moderation_router)
    return parent_router
