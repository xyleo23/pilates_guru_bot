"""AI assistant handler - free text and voice messages."""
import io
import logging
import os
import tempfile

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import ADMIN_TG_ID
from data.studio_info import STUDIO
from services.ai_assistant import get_ai_response

router = Router(name="ai")


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="💰 Цены", callback_data="menu:prices")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_escalation_keyboard() -> InlineKeyboardMarkup:
    """Кнопки для клиента при эскалации."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📞 Позвонить",
        url=f"tel:{STUDIO['phone'].replace(' ', '').replace('-', '')}"
    )
    tg = STUDIO["telegram"].lstrip("@")
    builder.button(text="✉️ Написать в TG", url=f"https://t.me/{tg}")
    return builder.as_markup()


async def _send_escalation(message: Message, state: FSMContext) -> None:
    """Отправить клиенту сообщение с кнопками и уведомить админа."""
    await message.answer(
        "_Марина:_ Для этого вопроса лучше связаться с нами напрямую 🙏",
        reply_markup=get_escalation_keyboard(),
        parse_mode="Markdown"
    )

    # Уведомить админа с контекстом диалога
    data = await state.get_data()
    history = data.get("chat_history", [])
    client_name = data.get("client_name", "")

    lines = ["🔄 *Эскалация* — клиент нуждается в личном ответе\n"]
    user_id = message.from_user.id if message.from_user else "?"
    username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else ""
    lines.append(f"User ID: `{user_id}` {username}")
    if client_name:
        lines.append(f"Имя: {client_name}")
    lines.append(f"\nПоследнее сообщение: _{message.text}_")
    if history:
        lines.append("\nКонтекст:")
        for h in history[-4:]:
            role = "👤" if h["role"] == "user" else "🤖"
            lines.append(f"{role} {h['content'][:200]}")

    try:
        await message.bot.send_message(
            chat_id=ADMIN_TG_ID,
            text="\n".join(lines),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Notify admin failed: {e}")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("chat_history", [])

    await message.bot.send_chat_action(
        chat_id=message.chat.id, action="typing"
    )

    result = await get_ai_response(
        message.text,
        history,
        client_name=data.get("client_name")
    )

    if result["type"] == "escalate":
        await _send_escalation(message, state)
        return

    if result["type"] == "fallback":
        text = (
            "Для записи воспользуйтесь кнопкой меню, "
            f"или позвоните: {STUDIO['phone']}"
        )
    else:
        text = result["text"]

    if result["type"] == "answer":
        history.append({"role": "user", "content": message.text})
        history.append({"role": "assistant", "content": result["text"]})
        if len(history) > 10:
            history = history[-10:]
        await state.update_data(chat_history=history)

    name = STUDIO["admin_name"]
    await message.answer(
        f"_{name}:_ {text}",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    from config import OPENAI_API_KEY
    from openai import AsyncOpenAI

    if not OPENAI_API_KEY:
        await message.answer(
            "_Марина:_ Пожалуйста, напишите ваш вопрос текстом 🙏",
            parse_mode="Markdown"
        )
        return

    await message.bot.send_chat_action(
        chat_id=message.chat.id, action="typing"
    )

    # Скачать голосовое сообщение
    voice = message.voice
    file = await message.bot.get_file(voice.file_id)
    file_bytes = await message.bot.download_file(file.file_path)

    # Распознать через Whisper
    try:
        oai = AsyncOpenAI(api_key=OPENAI_API_KEY)
        transcript = await oai.audio.transcriptions.create(
            model="whisper-1",
            file=("voice.ogg", file_bytes, "audio/ogg"),
            language="ru"
        )
        recognized_text = transcript.text
    except Exception as e:
        logging.error(f"Whisper error: {e}")
        await message.answer(
            "_Марина:_ Не удалось распознать голосовое. "
            "Напишите текстом — отвечу сразу! 🙏",
            parse_mode="Markdown"
        )
        return

    # Показать клиенту что распознали
    await message.answer(
        f"🎤 Распознано: _{recognized_text}_",
        parse_mode="Markdown"
    )

    # Обработать как обычное текстовое сообщение
    message.text = recognized_text
    await handle_free_text(message, state)
