"""FAQ handler."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.studio_info import FAQ, PRICES, PROMOS, STUDIO

router = Router(name="faq")

# Маппинг ключей FAQ на читаемые вопросы
FAQ_QUESTIONS = {
    "equipment": "Какое оборудование в студии?",
    "newbie": "Как записаться впервые?",
    "cancel_policy": "Отмена и перенос занятий",
    "what_to_bring": "Что взять с собой?",
    "late": "Что делать при опоздании?",
    "parking": "Парковка",
    "pregnancy": "Беременность и особые состояния",
    "contraindications": "Противопоказания",
    "payment": "Как оплатить?",
    "subscription": "Как работают абонементы?",
}


def _faq_list():
    """Convert FAQ dict to list of (question, answer, idx) for display."""
    return [
        (FAQ_QUESTIONS.get(k, k.replace("_", " ").title()), v, i)
        for i, (k, v) in enumerate(FAQ.items())
    ]


def get_faq_keyboard():
    """Build FAQ list keyboard."""
    builder = InlineKeyboardBuilder()
    for q, _a, i in _faq_list():
        builder.button(text=(q[:50] + "…") if len(q) > 50 else q, callback_data=f"faq:{i}")
    builder.button(text="🎁 Акции", callback_data="menu:promos")
    builder.button(text="📋 Мои записи", callback_data="menu:my_records")
    builder.button(text="◀️ Назад в меню", callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "menu:prices")
async def show_prices(callback: CallbackQuery):
    """Show price list."""
    lines = ["*Цены Pilates Guru:*\n"]
    for category in PRICES.values():
        for item in category:
            lines.append(f"• {item['name']}: {item['price']} ₽")
    lines.append("\nДля записи нажмите «Записаться».")
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "menu:faq")
async def show_faq_list(callback: CallbackQuery):
    """Show FAQ questions list."""
    text = "Часто задаваемые вопросы:\n\nВыберите вопрос:"
    builder = InlineKeyboardBuilder()
    for q, _a, i in _faq_list():
        builder.button(text=q[:45] + ("…" if len(q) > 45 else ""), callback_data=f"faq:{i}")
    builder.button(text="🎁 Акции", callback_data="menu:promos")
    builder.button(text="📋 Мои записи", callback_data="menu:my_records")
    builder.button(text="◀️ Назад в меню", callback_data="menu:main")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "menu:contacts")
async def show_contacts(callback: CallbackQuery):
    """Show studio contacts."""
    s = STUDIO
    text = (
        f"*{s['name']}*\n\n"
        f"📍 Адрес: {s['address']}\n"
        f"🚇 {s['metro']}\n"
        f"🕐 {s['schedule']}\n\n"
        f"📞 Телефон: {s['phone']}\n"
        f"✉️ Telegram: {s['telegram']}\n"
        f"📸 Instagram: {s.get('instagram', s['telegram'])}\n"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "menu:promos")
async def show_promos(callback: CallbackQuery):
    """Show promotions text from PROMOS."""
    lines = ["*Акции Pilates Guru:*\n"]
    for p in PROMOS:
        title = p.get("title", "")
        details = p.get("details", "")
        lines.append(f"• *{title}*\n{details}\n")
    text = "\n".join(lines)
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("faq:"))
async def show_faq_answer(callback: CallbackQuery):
    """Show FAQ answer for selected question."""
    idx = int(callback.data.split(":")[1])
    items = _faq_list()
    if 0 <= idx < len(items):
        q, a, _ = items[idx]
        text = f"*{q}*\n\n{a}"
    else:
        text = "Вопрос не найден."

    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ К списку вопросов", callback_data="menu:faq")
    builder.button(text="🏠 В главное меню", callback_data="menu:main")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()
