"""Start command and main menu handler."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.studio_info import STUDIO_NAME, STUDIO_DESCRIPTION

router = Router(name="start")


def get_main_keyboard():
    """Build main menu inline keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Расписание", callback_data="menu:schedule")
    builder.button(text="❓ FAQ", callback_data="menu:faq")
    builder.button(text="📅 Записаться на занятие", callback_data="menu:booking")
    builder.adjust(1)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    text = (
        f"Namaste! 🙏\n\n"
        f"Добро пожаловать в студию пилатеса *{STUDIO_NAME}*!\n\n"
        f"{STUDIO_DESCRIPTION}\n\n"
        f"Выберите действие:"
    )
    await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")


@router.callback_query(F.data == "menu:main")
async def back_to_main(callback: CallbackQuery):
    """Return to main menu."""
    text = (
        f"*{STUDIO_NAME}*\n\n"
        f"{STUDIO_DESCRIPTION}\n\n"
        f"Выберите действие:"
    )
    await callback.message.edit_text(
        text, reply_markup=get_main_keyboard(), parse_mode="Markdown"
    )
    await callback.answer()
