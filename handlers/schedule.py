"""Schedule handler - shows available classes from YClients."""
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.yclients import YClientsService
from config import YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
from data.studio_info import TRAINERS

router = Router(name="schedule")

yclients = YClientsService(
    YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, str(YCLIENTS_COMPANY_ID)
)


@router.callback_query(F.data == "menu:schedule")
async def show_schedule(callback: CallbackQuery):
    """Show schedule - available dates and services."""
    await callback.answer()
    msg = await callback.message.answer("⏳ Загружаю расписание...")

    try:
        services = await yclients.get_services()
        staff = await yclients.get_staff()
        if not staff:
            staff = [{"id": i + 1, "name": name} for i, name in enumerate(TRAINERS)]
        dates = await yclients.get_available_dates()

        if not dates and not services:
            text = (
                "К сожалению, в данный момент нет доступных занятий для записи.\n\n"
                "Пожалуйста, свяжитесь с нами для уточнения расписания."
            )
        else:
            text = "*Расписание Pilates Guru*\n\n"
            if services:
                text += "*Услуги:*\n"
                for s in services[:10]:
                    title = s.get("title") or s.get("booking_title") or "Услуга"
                    price = s.get("price_min") or s.get("price_max")
                    dur = s.get("duration", 0)
                    mins = dur // 60 if isinstance(dur, (int, float)) else 0
                    text += f"• {title}"
                    if price:
                        text += f" — от {price} ₽"
                    if mins:
                        text += f" ({mins} мин)"
                    text += "\n"
            if dates:
                text += "\n*Ближайшие доступные даты:*\n"
                for ts in dates[:7]:
                    dt = datetime.fromtimestamp(ts)
                    text += f"• {dt.strftime('%d.%m.%Y')}\n"
            text += "\nИспользуйте кнопку «Записаться», чтобы выбрать время."

        builder = InlineKeyboardBuilder()
        builder.button(text="📅 Записаться на занятие", callback_data="menu:booking")
        builder.button(text="◀️ Назад в меню", callback_data="menu:main")
        builder.adjust(1)

        await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(
            f"Не удалось загрузить расписание.\n"
            f"Ошибка: {str(e)}\n\n"
            f"Попробуйте позже или свяжитесь с администратором."
        )
