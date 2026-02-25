"""AI assistant handler - free text and voice messages."""
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from services.ai_assistant import get_ai_response, get_admin_name

router = Router(name="ai")

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="💰 Цены", callback_data="menu:prices")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    builder.adjust(2, 1)
    return builder.as_markup()

@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("chat_history", [])

    # Показываем "печатает..."
    await message.bot.send_chat_action(
        chat_id=message.chat.id, action="typing"
    )

    response = await get_ai_response(message.text, history)

    # Сохраняем историю (максимум 10 сообщений)
    history.append({"role": "user", "content": message.text})
    history.append({"role": "assistant", "content": response})
    if len(history) > 10:
        history = history[-10:]
    await state.update_data(chat_history=history)

    name = get_admin_name()
    await message.answer(
        f"_{name}:_ {response}",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    """Голосовые сообщения — вежливый отказ с предложением написать"""
    name = get_admin_name()
    await message.answer(
        f"_{name}:_ К сожалению, голосовые сообщения пока не поддерживаются 🙏 "
        f"Напишите ваш вопрос текстом — отвечу сразу!",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
