import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_TG_ID

router = Router()

# Ссылки для оставления отзывов
YANDEX_MAPS_URL = "https://yandex.ru/maps/org/pilates_guru/69364383319/reviews/"
DGIS_URL = "https://2gis.ru/lyubertsy/firm/70000001094262672"


class FeedbackStates(StatesGroup):
    waiting_bad_text = State()


@router.callback_query(F.data.startswith("feedback_good:"))
async def feedback_good(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭐ Яндекс Карты",
                    url=YANDEX_MAPS_URL,
                ),
                InlineKeyboardButton(
                    text="⭐ 2ГИС",
                    url=DGIS_URL,
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Не хочу оставлять отзыв",
                    callback_data="feedback_skip",
                ),
            ],
        ]
    )

    await callback.message.edit_text(
        "Спасибо! Рады, что тренировка прошла хорошо 🙏\n\n"
        "Нам очень важно ваше мнение — если не сложно, "
        "оставьте короткий отзыв. Это помогает нам развиваться "
        "и поможет другим людям найти *Pilates Guru* ❤️",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_bad:"))
async def feedback_bad(callback: CallbackQuery):
    record_id = callback.data.split(":")[1]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Написать руководителю",
                    callback_data=f"feedback_write:{record_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Не сейчас",
                    callback_data="feedback_skip",
                ),
            ],
        ]
    )

    await callback.message.edit_text(
        "Жаль, что что-то пошло не так 😔\n\n"
        "Расскажите нам — это поможет стать лучше. "
        "Ваше сообщение получит руководитель лично:",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_write:"))
async def feedback_write(callback: CallbackQuery, state: FSMContext):
    record_id = callback.data.split(":")[1]
    await state.set_state(FeedbackStates.waiting_bad_text)
    await state.update_data(feedback_record_id=record_id)
    await callback.message.edit_text(
        "📝 Напишите, что не понравилось или что можно улучшить.\n\n"
        "Ваше сообщение получит только руководитель студии."
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_skip")
async def feedback_skip(callback: CallbackQuery):
    await callback.message.edit_text(
        "Хорошо, до следующей тренировки! 🙏"
    )
    await callback.answer()


@router.message(FeedbackStates.waiting_bad_text)
async def receive_bad_feedback(message: Message, state: FSMContext):
    data = await state.get_data()
    record_id = data.get("feedback_record_id", "?")
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    full_name = message.from_user.full_name or ""

    if ADMIN_TG_ID:
        admin_text = (
            f"⚠️ *Негативный отзыв — Pilates Guru*\n\n"
            f"Запись: #{record_id}\n"
            f"Клиент: {full_name} (@{username}, id: {user_id})\n\n"
            f"💬 *Отзыв:*\n{message.text}"
        )
        try:
            await message.bot.send_message(
                chat_id=ADMIN_TG_ID,
                text=admin_text,
                parse_mode="Markdown",
            )
        except Exception as e:
            logging.warning(f"Не удалось отправить отзыв админу: {e}")

    await state.clear()
    await message.answer(
        "Спасибо, что написали 🙏\n\n"
        "Руководитель студии лично ознакомится с вашим отзывом. "
        "Мы обязательно учтём это и станем лучше ❤️"
    )
