"""Start command and main menu handler."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.studio_info import STUDIO

router = Router(name="start")


def get_share_phone_keyboard() -> ReplyKeyboardMarkup:
    """Single button: Share Phone (request_contact)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def get_premium_reply_keyboard() -> ReplyKeyboardMarkup:
    """Premium minimalist reply keyboard - persistent bottom menu."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ЗАПИСАТЬСЯ")],
            [KeyboardButton(text="ПРАЙС-ЛИСТ"), KeyboardButton(text="МОЙ ПРОФИЛЬ")]
        ],
        resize_keyboard=True,
    )


def get_main_keyboard():
    """Build main menu inline keyboard (1 столбец)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Записаться на тренировку", callback_data="menu:booking")
    builder.button(text="Мои записи", callback_data="menu:my_records")
    builder.button(text="Подобрать тренера", callback_data="menu:match_trainer")
    builder.button(text="Цены и услуги", callback_data="menu:prices")
    builder.button(text="Акции", callback_data="menu:promos")
    builder.button(text="Частые вопросы", callback_data="menu:faq")
    builder.button(text="Контакты", callback_data="menu:contacts")
    builder.adjust(1)
    return builder.as_markup()


def get_onboarding_main_keyboard():
    """Simplified main menu for returning/new clients: Записаться, Цены, Мои записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Записаться", callback_data="menu:booking")
    builder.button(text="Цены", callback_data="menu:prices")
    builder.button(text="Мои записи", callback_data="menu:my_records")
    builder.adjust(1)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message):
    """Handle /start — single greeting, Share Phone only."""
    text = (
        "Добро пожаловать в студию Pilates Guru.\n\n"
        "Меня зовут Марина, я ваш виртуальный администратор. "
        "Чтобы я могла проверить ваши абонементы или подобрать тренировку, "
        "пожалуйста, поделитесь номером телефона."
    )
    await message.answer(
        text,
        reply_markup=get_share_phone_keyboard(),
    )


@router.message(Command("book"))
async def cmd_book(message):
    """Handle /book command - redirect to booking."""
    from handlers.booking import start_booking_from_command
    await start_booking_from_command(message)


@router.message(Command("my_bookings"))
async def cmd_my_bookings(message):
    """Handle /my_bookings command."""
    from handlers.manage_booking import router as manage_router
    # Trigger the my records handler
    await message.answer(
        "Здесь будет отображена информация о ваших записях.",
        reply_markup=get_premium_reply_keyboard()
    )


@router.message(Command("prices"))
async def cmd_prices(message):
    """Handle /prices command."""
    from handlers.faq import show_prices
    await show_prices(message)


@router.message(Command("help"))
async def cmd_help(message):
    """Handle /help command - contact admin."""
    await message.answer(
        f"Связаться с администратором:\n\n"
        f"Телефон: {STUDIO['phone']}\n"
        f"Telegram: {STUDIO['telegram']}\n"
        f"Instagram: {STUDIO['instagram']}",
        reply_markup=get_premium_reply_keyboard()
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


@router.message(F.text == "МОЙ ПРОФИЛЬ")
async def handle_profile_button(message):
    """Handle МОЙ ПРОФИЛЬ button from reply keyboard."""
    await message.answer(
        f"*{STUDIO['name']}*\n\n"
        f"Помогу записаться на тренировку, расскажу о ценах и расписании.\n\n"
        f"Выберите действие:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
