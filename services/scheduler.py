from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import pytz
from datetime import datetime, timedelta

MSK = pytz.timezone("Europe/Moscow")
scheduler = AsyncIOScheduler(timezone=MSK)


def get_custom_field(client: dict, field_name: str) -> str | None:
    """Извлечь значение custom_field по title из списка."""
    cf = client.get("custom_fields")
    if not cf:
        return None
    if isinstance(cf, dict):
        return cf.get(field_name)
    if isinstance(cf, list):
        for item in cf:
            if isinstance(item, dict):
                title = item.get("title", "") or item.get("name", "")
                if title and str(title).lower() == field_name.lower():
                    return item.get("value")
    return None


def start_scheduler(bot, yclients):
    scheduler.add_job(
        send_reminders,
        trigger=IntervalTrigger(hours=1),
        args=[bot, yclients],
        id="reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_feedback_requests,
        trigger=IntervalTrigger(hours=1),
        args=[bot, yclients],
        id="feedback",
        replace_existing=True,
    )
    scheduler.start()
    logging.info("✅ Scheduler started")


async def send_reminders(bot, yclients):
    """
    Раз в час проверяет записи на следующие 24 часа
    и шлёт напоминание тем, кому ещё не отправляли.
    """
    from services.notified_store import is_notified, mark_notified

    now = datetime.now(tz=MSK)
    target_start = now + timedelta(hours=23)
    target_end = now + timedelta(hours=25)

    try:
        # Получить все записи студии на ближайшие 25 часов
        # YClients: GET /records/{company_id}
        # params: start_date, end_date (формат YYYY-MM-DD)
        data = await yclients._request(
            "GET",
            f"/records/{yclients.company_id}",
            params={
                "start_date": (target_start - timedelta(days=1)).strftime("%Y-%m-%d"),
                "end_date": (target_end + timedelta(days=1)).strftime("%Y-%m-%d"),
                "count": 200,
            },
        )
        records = data.get("data", [])
    except Exception as e:
        logging.warning(f"Scheduler: не удалось получить записи — {e}")
        return

    for record in records:
        try:
            record_id = record.get("id")
            dt_str = record.get("date")  # "YYYY-MM-DD HH:MM:SS"
            client = record.get("client", {})
            tg_id = client.get("custom_fields", {}).get("telegram_id")
            client_name = client.get("name", "")
            staff_name = (record.get("staff") or {}).get("name", "тренер")
            service_name = ""
            services = record.get("services", [])
            if services:
                service_name = services[0].get("title", "")

            if not tg_id or not record_id or not dt_str:
                continue

            # Проверить попадает ли запись в окно 23–25 часов
            dt = MSK.localize(datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S"))
            diff = (dt - now).total_seconds() / 3600
            if not (23 <= diff <= 25):
                continue

            # Не отправлять дважды
            if is_notified(record_id, "reminder"):
                continue

            date_fmt = dt.strftime("%d.%m.%Y")
            time_fmt = dt.strftime("%H:%M")

            text = (
                f"⏰ *Напоминание о тренировке в Pilates Guru*\n\n"
                f"Завтра, {date_fmt} в {time_fmt}\n"
                f"Тренер: {staff_name}\n"
                f"Занятие: {service_name}\n\n"
                f"Если нужно отменить или перенести — сделайте это "
                f"за 20+ часов до начала."
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❌ Отменить/Перенести",
                            callback_data=f"manage:{record_id}",
                        ),
                        InlineKeyboardButton(
                            text="✅ Буду",
                            callback_data=f"remind_ok:{record_id}",
                        ),
                    ]
                ]
            )

            await bot.send_message(
                chat_id=int(tg_id),
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            mark_notified(record_id, "reminder")
            logging.info(f"Reminder sent: tg_id={tg_id}, record={record_id}")

        except Exception as e:
            logging.warning(f"Scheduler: ошибка при отправке напоминания — {e}")


async def send_feedback_requests(bot, yclients):
    """
    Через 2 часа после окончания тренировки спрашивает как прошло.
    """
    from services.notified_store import is_notified, mark_notified
    from data.studio_info import RULES

    now = datetime.now(tz=MSK)
    # Записи которые завершились 1.5–2.5 часа назад
    window_start = now - timedelta(hours=2, minutes=30)
    window_end = now - timedelta(hours=1, minutes=30)

    try:
        data = await yclients._request(
            "GET",
            f"/records/{yclients.company_id}",
            params={
                "start_date": (window_start - timedelta(days=1)).strftime("%Y-%m-%d"),
                "end_date": (window_end + timedelta(days=1)).strftime("%Y-%m-%d"),
                "count": 200,
            },
        )
        records = data.get("data", [])
    except Exception as e:
        logging.warning(f"Feedback scheduler error: {e}")
        return

    duration = RULES.get("session_duration_min", 55)

    for record in records:
        try:
            record_id = record.get("id")
            dt_str = record.get("datetime") or record.get("date")
            client = record.get("client", {})
            tg_id = get_custom_field(client, "telegram_id")
            client_name = client.get("name", "")
            staff_name = (record.get("staff") or {}).get("name", "тренера")

            if not tg_id or not record_id or not dt_str:
                continue

            dt_start = MSK.localize(
                datetime.strptime(dt_str[:19], "%Y-%m-%d %H:%M:%S")
            )
            dt_end = dt_start + timedelta(minutes=duration)

            diff = (now - dt_end).total_seconds() / 3600
            if not (1.5 <= diff <= 2.5):
                continue

            if is_notified(record_id, "feedback"):
                continue

            first_name = client_name.split()[0] if client_name else ""
            greeting = f", {first_name}" if first_name else ""

            text = (
                f"👋 Как прошла тренировка в *Pilates Guru*{greeting}?\n\n"
                f"Занятие с тренером {staff_name} только что завершилось. "
                f"Оцените, пожалуйста:"
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="👍 Всё отлично!",
                            callback_data=f"feedback_good:{record_id}",
                        ),
                        InlineKeyboardButton(
                            text="👎 Есть замечания",
                            callback_data=f"feedback_bad:{record_id}",
                        ),
                    ]
                ]
            )

            await bot.send_message(
                chat_id=int(tg_id),
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            mark_notified(record_id, "feedback")

        except Exception as e:
            logging.warning(f"Feedback send error: {e}")
