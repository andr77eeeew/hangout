from aiogram import Router
from bot.handlers.link import router as link_router
from bot.handlers.notifications import router as notifications_router
from bot.handlers.start import router as start_router


def get_handlers_router() -> Router:
    parent_router = Router()
    parent_router.include_router(start_router)
    parent_router.include_router(link_router)
    parent_router.include_router(notifications_router)
    return parent_router
