"""FAQ handler."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.studio_info import FAQ, PRICES

router = Router(name="faq")


def get_faq_keyboard():
    """Build FAQ list keyboard."""
    builder = InlineKeyboardBuilder()
    for i, item in enumerate(FAQ):
        builder.button(text=item["question"][:50] + "…", callback_data=f"faq:{i}")
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
    for i, item in enumerate(FAQ):
        q = item["question"]
        builder.button(text=q[:45] + ("…" if len(q) > 45 else ""), callback_data=f"faq:{i}")
    builder.button(text="◀️ Назад в меню", callback_data="menu:main")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("faq:"))
async def show_faq_answer(callback: CallbackQuery):
    """Show FAQ answer for selected question."""
    idx = int(callback.data.split(":")[1])
    if 0 <= idx < len(FAQ):
        item = FAQ[idx]
        text = f"*{item['question']}*\n\n{item['answer']}"
    else:
        text = "Вопрос не найден."

    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ К списку вопросов", callback_data="menu:faq")
    builder.button(text="🏠 В главное меню", callback_data="menu:main")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()
