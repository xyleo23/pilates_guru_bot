"""MVP Mock Booking Flow - Premium Demo with YooKassa Test Payments."""
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.payment import create_payment, check_payment
from handlers.start import get_premium_reply_keyboard
from data.studio_info import STUDIO

router = Router(name="booking")


class BookingStates(StatesGroup):
    """FSM states for MVP booking flow."""
    choose_service = State()
    choose_staff = State()
    choose_time = State()
    confirm = State()
    payment = State()


# MVP HARDCODED DATA
MOCK_SERVICES = [
    {"id": 1, "name": "Персональная тренировка", "price": 3500, "duration": 55},
    {"id": 2, "name": "Сплит-тренировка", "price": 4000, "duration": 55},
]

MOCK_STAFF = [
    {"id": 1, "name": "Мария (Топ-тренер)"},
    {"id": 2, "name": "Анна"},
    {"id": 3, "name": "Елена"},
]

MOCK_TIME_SLOTS = [
    {"id": 1, "label": "Завтра, 10:00", "datetime": (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)},
    {"id": 2, "label": "Завтра, 14:00", "datetime": (datetime.now() + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)},
    {"id": 3, "label": "Послезавтра, 18:00", "datetime": (datetime.now() + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)},
]


# ENTRY POINTS
@router.message(F.text == "ЗАПИСАТЬСЯ")
async def start_booking_from_button(message: Message, state: FSMContext):
    """Handle ЗАПИСАТЬСЯ button from reply keyboard."""
    await show_services(message, state, from_callback=False)


@router.message(Command("book"))
async def start_booking_from_command(message: Message, state: FSMContext = None):
    """Handle /book command."""
    if state:
        await show_services(message, state, from_callback=False)
    else:
        await message.answer(
            "Для записи используйте кнопку ЗАПИСАТЬСЯ в меню.",
            reply_markup=get_premium_reply_keyboard()
        )


@router.callback_query(F.data == "menu:booking")
async def start_booking_callback(callback: CallbackQuery, state: FSMContext):
    """Handle booking callback from inline menu."""
    await callback.answer()
    await show_services(callback, state, from_callback=True)


# STEP 1: SHOW SERVICES
async def show_services(msg_or_cb, state: FSMContext, from_callback: bool):
    """Show hardcoded services."""
    await state.clear()
    await state.set_state(BookingStates.choose_service)
    
    builder = InlineKeyboardBuilder()
    for service in MOCK_SERVICES:
        builder.button(
            text=f"{service['name']} — {service['price']} ₽",
            callback_data=f"book_svc:{service['id']}"
        )
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    text = "*Выберите тип тренировки:*"
    
    if from_callback:
        await msg_or_cb.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    else:
        await msg_or_cb.answer(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )


# STEP 2: SERVICE SELECTED -> SHOW STAFF
@router.callback_query(BookingStates.choose_service, F.data.startswith("book_svc:"))
async def service_selected(callback: CallbackQuery, state: FSMContext):
    """User selected service, show staff."""
    service_id = int(callback.data.split(":")[1])
    service = next((s for s in MOCK_SERVICES if s["id"] == service_id), None)
    
    if not service:
        await callback.answer("Ошибка выбора услуги", show_alert=True)
        return
    
    await state.update_data(
        service_id=service_id,
        service_name=service["name"],
        service_price=service["price"]
    )
    await state.set_state(BookingStates.choose_staff)
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    for staff in MOCK_STAFF:
        builder.button(
            text=staff["name"],
            callback_data=f"book_staff:{staff['id']}"
        )
    builder.button(text="Назад", callback_data="book_back:service")
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "*Выберите тренера:*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# STEP 3: STAFF SELECTED -> SHOW TIME SLOTS
@router.callback_query(BookingStates.choose_staff, F.data.startswith("book_staff:"))
async def staff_selected(callback: CallbackQuery, state: FSMContext):
    """User selected staff, show time slots."""
    staff_id = int(callback.data.split(":")[1])
    staff = next((s for s in MOCK_STAFF if s["id"] == staff_id), None)
    
    if not staff:
        await callback.answer("Ошибка выбора тренера", show_alert=True)
        return
    
    await state.update_data(
        staff_id=staff_id,
        staff_name=staff["name"]
    )
    await state.set_state(BookingStates.choose_time)
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    for slot in MOCK_TIME_SLOTS:
        builder.button(
            text=slot["label"],
            callback_data=f"book_time:{slot['id']}"
        )
    builder.button(text="Назад", callback_data="book_back:staff")
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "*Выберите время:*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# STEP 4: TIME SELECTED -> SHOW SUMMARY & PAYMENT
@router.callback_query(BookingStates.choose_time, F.data.startswith("book_time:"))
async def time_selected(callback: CallbackQuery, state: FSMContext):
    """User selected time, show summary and payment button."""
    time_id = int(callback.data.split(":")[1])
    time_slot = next((t for t in MOCK_TIME_SLOTS if t["id"] == time_id), None)
    
    if not time_slot:
        await callback.answer("Ошибка выбора времени", show_alert=True)
        return
    
    await state.update_data(
        time_id=time_id,
        time_label=time_slot["label"],
        time_datetime=time_slot["datetime"].isoformat()
    )
    await state.set_state(BookingStates.confirm)
    await callback.answer()
    
    data = await state.get_data()
    service_name = data["service_name"]
    staff_name = data["staff_name"]
    time_label = data["time_label"]
    price = data["service_price"]
    
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить (Демо)", callback_data="book_pay")
    builder.button(text="Назад", callback_data="book_back:time")
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    text = (
        f"*Выбрано:*\n\n"
        f"Услуга: {service_name}\n"
        f"Тренер: {staff_name}\n"
        f"Время: {time_label}\n\n"
        f"*Сумма: {price} ₽*\n\n"
        f"Оплатить?"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# STEP 5: CREATE YOOKASSA PAYMENT
@router.callback_query(BookingStates.confirm, F.data == "book_pay")
async def create_booking_payment(callback: CallbackQuery, state: FSMContext):
    """Create YooKassa test payment."""
    await callback.answer()
    data = await state.get_data()
    
    service_name = data["service_name"]
    price = data["service_price"]
    staff_name = data["staff_name"]
    time_label = data["time_label"]
    
    user_id = callback.from_user.id if callback.from_user else 0
    
    metadata = {
        "service_id": str(data["service_id"]),
        "staff_id": str(data["staff_id"]),
        "time_id": str(data["time_id"]),
        "tg_user_id": str(user_id),
        "demo": "true"
    }
    
    payment = await create_payment(
        amount=float(price),
        description=f"{service_name} у {staff_name}",
        metadata=metadata,
    )
    
    if not payment:
        await callback.message.edit_text(
            "Ошибка при создании платежа. Попробуйте позже.",
            reply_markup=get_premium_reply_keyboard()
        )
        await state.clear()
        return
    
    payment_id = payment["id"]
    confirmation_url = payment["confirmation_url"]
    await state.update_data(payment_id=payment_id)
    await state.set_state(BookingStates.payment)
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Оплатить {price} ₽", url=confirmation_url)
    builder.button(
        text="Проверить оплату",
        callback_data=f"check_payment:{payment_id}"
    )
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    text = (
        f"*Оплата:*\n\n"
        f"Услуга: {service_name}\n"
        f"Тренер: {staff_name}\n"
        f"Время: {time_label}\n\n"
        f"*Сумма: {price} ₽*\n\n"
        f"Нажмите кнопку «Оплатить» для перехода к оплате.\n"
        f"После оплаты вернитесь и нажмите «Проверить оплату».\n\n"
        f"_Используйте тестовую карту: 1111 1111 1111 1026_"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# STEP 6: CHECK PAYMENT STATUS
@router.callback_query(BookingStates.payment, F.data.startswith("check_payment:"))
async def handle_check_payment(callback: CallbackQuery, state: FSMContext):
    """Check YooKassa payment status."""
    payment_id = callback.data.split(":", 1)[1]
    await callback.answer()
    
    status = await check_payment(payment_id)
    
    if status == "succeeded":
        data = await state.get_data()
        service_name = data["service_name"]
        staff_name = data["staff_name"]
        time_label = data["time_label"]
        
        await state.clear()
        
        text = (
            f"*Оплата успешно получена!*\n\n"
            f"Вы записаны на демо-тренировку:\n\n"
            f"Услуга: {service_name}\n"
            f"Тренер: {staff_name}\n"
            f"Время: {time_label}\n\n"
            f"Ждём вас на занятии!\n\n"
            f"Адрес: {STUDIO['address']}\n"
            f"Телефон: {STUDIO['phone']}"
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="Markdown"
        )
        
        await callback.message.answer(
            "Используйте меню для дальнейших действий:",
            reply_markup=get_premium_reply_keyboard()
        )
        
    elif status == "pending":
        await callback.answer(
            "Оплата ещё не прошла. Попробуйте через минуту.",
            show_alert=True
        )
    elif status == "canceled":
        await state.clear()
        await callback.message.edit_text(
            "Платёж отменён. Начните запись заново.",
        )
        await callback.message.answer(
            "Используйте меню:",
            reply_markup=get_premium_reply_keyboard()
        )
    else:
        await callback.answer(
            "Ошибка проверки платежа. Попробуйте ещё раз.",
            show_alert=True
        )


# NAVIGATION HANDLERS
@router.callback_query(F.data == "book_back:service")
async def back_to_service(callback: CallbackQuery, state: FSMContext):
    """Back to service selection."""
    await callback.answer()
    await show_services(callback, state, from_callback=True)


@router.callback_query(F.data == "book_back:staff")
async def back_to_staff(callback: CallbackQuery, state: FSMContext):
    """Back to staff selection."""
    data = await state.get_data()
    service_id = data.get("service_id")
    
    if not service_id:
        await callback.answer("Начните запись заново", show_alert=True)
        await show_services(callback, state, from_callback=True)
        return
    
    await state.set_state(BookingStates.choose_staff)
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    for staff in MOCK_STAFF:
        builder.button(
            text=staff["name"],
            callback_data=f"book_staff:{staff['id']}"
        )
    builder.button(text="Назад", callback_data="book_back:service")
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "*Выберите тренера:*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "book_back:time")
async def back_to_time(callback: CallbackQuery, state: FSMContext):
    """Back to time selection."""
    data = await state.get_data()
    staff_id = data.get("staff_id")
    
    if not staff_id:
        await callback.answer("Начните запись заново", show_alert=True)
        await show_services(callback, state, from_callback=True)
        return
    
    await state.set_state(BookingStates.choose_time)
    await callback.answer()
    
    builder = InlineKeyboardBuilder()
    for slot in MOCK_TIME_SLOTS:
        builder.button(
            text=slot["label"],
            callback_data=f"book_time:{slot['id']}"
        )
    builder.button(text="Назад", callback_data="book_back:staff")
    builder.button(text="Отменить", callback_data="book_cancel")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "*Выберите время:*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "book_cancel")
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    """Cancel booking flow."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "Запись отменена. Используйте меню для дальнейших действий."
    )
    await callback.message.answer(
        "Главное меню:",
        reply_markup=get_premium_reply_keyboard()
    )


# HANDLER FOR "ПРАЙС-ЛИСТ" BUTTON
@router.message(F.text == "ПРАЙС-ЛИСТ")
async def show_price_list(message: Message):
    """Show price list when user presses ПРАЙС-ЛИСТ button."""
    from data.studio_info import PRICES
    
    text_parts = ["*Услуги и цены:*\n"]
    
    text_parts.append("\n*Персональные тренировки:*")
    for item in PRICES.get("personal", []):
        note = f" ({item['note']})" if item.get("note") else ""
        text_parts.append(f"• {item['name']}: {item['price']} ₽{note}")
    
    text_parts.append("\n*Сплит-тренировки (2 человека):*")
    for item in PRICES.get("split", []):
        note = f" ({item['note']})" if item.get("note") else ""
        text_parts.append(f"• {item['name']}: {item['price']} ₽{note}")
    
    text_parts.append("\n*Групповые тренировки (до 4 человек):*")
    for item in PRICES.get("group", []):
        text_parts.append(f"• {item['name']}: {item['price']} ₽")
    
    text_parts.append(f"\n\nДля записи используйте кнопку ЗАПИСАТЬСЯ.")
    
    await message.answer(
        "\n".join(text_parts),
        parse_mode="Markdown",
        reply_markup=get_premium_reply_keyboard()
    )
