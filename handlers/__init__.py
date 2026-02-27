from aiogram import Router
from handlers.start import router as start_router
from handlers.contact import router as contact_router
from handlers.faq import router as faq_router
from handlers.schedule import router as schedule_router
from handlers.booking import router as booking_router
from handlers.manage_booking import router as manage_router
from handlers.feedback import router as feedback_router
from handlers.trainer_match import router as match_router
from handlers.ai_handler import router as ai_router

def setup_handlers() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(contact_router)
    router.include_router(faq_router)
    router.include_router(schedule_router)
    router.include_router(booking_router)
    router.include_router(manage_router)
    router.include_router(feedback_router)
    router.include_router(match_router)
    router.include_router(ai_router)  # последним!
    return router
