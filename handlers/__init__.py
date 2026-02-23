"""Handlers package."""
from aiogram import Router

from .start import router as start_router
from .faq import router as faq_router
from .schedule import router as schedule_router
from .booking import router as booking_router


def setup_handlers() -> Router:
    """Register all handlers and return main router."""
    router = Router(name="main")
    router.include_router(start_router, tags=["start"])
    router.include_router(faq_router, tags=["faq"])
    router.include_router(schedule_router, tags=["schedule"])
    router.include_router(booking_router, tags=["booking"])
    return router
