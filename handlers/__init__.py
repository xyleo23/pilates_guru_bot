from aiogram import Router
from handlers.start import router as start_router
from handlers.faq import router as faq_router
from handlers.schedule import router as schedule_router
from handlers.booking import router as booking_router

def setup_handlers() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(faq_router)
    router.include_router(schedule_router)
    router.include_router(booking_router)
    return router
