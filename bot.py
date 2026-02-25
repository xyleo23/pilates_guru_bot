"""Pilates Guru Telegram Bot - entry point."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
from handlers import setup_handlers
from services.scheduler import start_scheduler
from services.yclients import YClientsService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Run the bot."""
    yclients = YClientsService(
        YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, str(YCLIENTS_COMPANY_ID)
    )
    ok = await yclients.check_connection()
    if ok:
        logger.info("✅ YClients подключён")
    else:
        logger.warning("⚠️ YClients недоступен — работаем с fallback данными")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_handlers())

    async def on_startup():
        start_scheduler(bot, yclients)

    logger.info("Starting Pilates Guru Bot...")
    await dp.start_polling(bot, on_startup=on_startup)


if __name__ == "__main__":
    asyncio.run(main())
