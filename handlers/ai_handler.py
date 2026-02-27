"""AI assistant handler — free text and voice messages (Marina agent)."""
import logging

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import OPENAI_API_KEY
from services.ai_agent import get_ai_response
from handlers.contact import NewClientStates

router = Router(name="ai")


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="💰 Цены и услуги", callback_data="menu:prices")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    builder.adjust(2, 1)
    return builder.as_markup()


@router.message(
    F.text & ~F.text.startswith("/"),
    ~StateFilter(NewClientStates),
)
async def handle_free_text(message: Message):
    """Catch-all for text: show typing, get AI response, send answer."""
    await message.bot.send_chat_action(
        chat_id=message.chat.id, action="typing"
    )

    user_id = message.from_user.id if message.from_user else 0
    ai_text = await get_ai_response(user_id, message.text or "")

    await message.answer(
        ai_text,
        reply_markup=get_main_menu_keyboard(),
    )


@router.message(F.voice)
async def handle_voice(message: Message):
    """Transcribe voice via Whisper, then process as text with AI agent."""
    if not OPENAI_API_KEY:
        await message.answer(
            "Пожалуйста, напишите ваш вопрос текстом 🙏",
        )
        return

    await message.bot.send_chat_action(
        chat_id=message.chat.id, action="typing"
    )

    voice = message.voice
    file = await message.bot.get_file(voice.file_id)
    file_bytes = await message.bot.download_file(file.file_path)

    try:
        from openai import AsyncOpenAI
        oai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        transcript = await oai.audio.transcriptions.create(
            model="whisper-1",
            file=("voice.ogg", file_bytes, "audio/ogg"),
            language="ru"
        )
        recognized_text = transcript.text or ""
    except Exception as e:
        logging.error("Whisper error: %s", e)
        await message.answer(
            "Не удалось распознать голосовое. "
            "Напишите текстом — отвечу сразу! 🙏",
        )
        return

    await message.answer(
        f"🎤 Распознано: _{recognized_text}_",
        parse_mode="Markdown"
    )

    # Process as text via AI agent
    message.text = recognized_text
    await handle_free_text(message)
