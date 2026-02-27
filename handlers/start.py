"""Start command and main menu handler."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.studio_info import STUDIO

router = Router(name="start")


def get_share_phone_keyboard() -> ReplyKeyboardMarkup:
    """Single button: Share Phone (request_contact)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_main_keyboard():
    """Build main menu inline keyboard (1 столбец)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться на тренировку", callback_data="menu:booking")
    builder.button(text="📋 Мои записи", callback_data="menu:my_records")
    builder.button(text="🎯 Подобрать тренера", callback_data="menu:match_trainer")
    builder.button(text="💰 Цены и услуги", callback_data="menu:prices")
    builder.button(text="🎁 Акции", callback_data="menu:promos")
    builder.button(text="❓ Частые вопросы", callback_data="menu:faq")
    builder.button(text="📍 Контакты", callback_data="menu:contacts")
    builder.adjust(1)
    return builder.as_markup()


def get_onboarding_main_keyboard():
    """Simplified main menu for returning/new clients: Записаться, Цены, Мои записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="💰 Цены", callback_data="menu:prices")
    builder.button(text="👤 Мои записи", callback_data="menu:my_records")
    builder.adjust(1)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message):
    """Handle /start — single greeting, Share Phone only."""
    text = (
        "Добро пожаловать в студию Pilates Guru! 🌸\n\n"
        "Меня зовут Марина, я ваш виртуальный администратор. "
        "Чтобы я могла проверить ваши абонементы или подобрать тренировку, "
        "пожалуйста, поделитесь номером телефона 👇"
    )
    await message.answer(
        text,
        reply_markup=get_share_phone_keyboard(),
    )


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Return to main menu."""
    await state.clear()
    text = (
        f"*{STUDIO['name']}*\n\n"
        f"Помогу записаться на тренировку, расскажу о ценах и расписании.\n\n"
        f"Выберите действие:"
    )
    await callback.message.edit_text(
        text, reply_markup=get_main_keyboard(), parse_mode="Markdown"
    )
    await callback.answer()
