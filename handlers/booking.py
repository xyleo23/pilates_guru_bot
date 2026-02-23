"""Booking handler - record a class via YClients."""
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.yclients import YClientsService
from config import YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID

router = Router(name="booking")

yclients = YClientsService(YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID)


class BookingStates(StatesGroup):
    """FSM states for booking flow."""
    choose_service = State()
    choose_staff = State()
    choose_date = State()
    choose_time = State()
    enter_name = State()
    enter_phone = State()
    enter_email = State()
    confirm = State()


@router.callback_query(F.data == "menu:booking")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    """Start booking flow."""
    await state.clear()
    await callback.answer()

    try:
        services = await yclients.get_services()
        if not services:
            await callback.message.answer(
                "К сожалению, сейчас нет доступных услуг для записи. "
                "Попробуйте позже или свяжитесь с нами."
            )
            return

        builder = InlineKeyboardBuilder()
        for s in services[:15]:
            sid = s.get("id") or s.get("api_id")
            title = (s.get("title") or s.get("booking_title") or "Услуга")[:40]
            builder.button(text=title, callback_data=f"book_svc:{sid}")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(1)

        await state.update_data(services=services)
        await state.set_state(BookingStates.choose_service)
        await callback.message.edit_text(
            "Выберите тип занятия:",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка при загрузке услуг: {e}")


@router.callback_query(BookingStates.choose_service, F.data.startswith("book_svc:"))
async def chose_service(callback: CallbackQuery, state: FSMContext):
    """User chose service, show staff."""
    service_id = int(callback.data.split(":")[1])
    await state.update_data(service_id=service_id)
    await callback.answer()

    try:
        staff = await yclients.get_staff(service_id=service_id)
        staff = [s for s in staff if s.get("bookable", True)]

        if not staff:
            await callback.message.edit_text(
                "Нет доступных инструкторов для этой услуги. Выберите другую услугу."
            )
            await start_booking(callback, state)
            return

        builder = InlineKeyboardBuilder()
        for s in staff[:10]:
            sid = s.get("id")
            name = (s.get("name") or "Инструктор")[:35]
            builder.button(text=name, callback_data=f"book_staff:{sid}")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(1)

        await state.set_state(BookingStates.choose_staff)
        await callback.message.edit_text(
            "Выберите инструктора:",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(BookingStates.choose_staff, F.data.startswith("book_staff:"))
async def chose_staff(callback: CallbackQuery, state: FSMContext):
    """User chose staff, show dates."""
    staff_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    service_id = data.get("service_id")

    await state.update_data(staff_id=staff_id)
    await callback.answer()

    try:
        dates = await yclients.get_available_dates(
            staff_id=staff_id, service_id=service_id
        )
        if not dates:
            await callback.message.edit_text(
                "Нет свободных дат. Попробуйте другого инструктора."
            )
            return

        builder = InlineKeyboardBuilder()
        for ts in dates[:14]:
            dt = datetime.fromtimestamp(ts)
            builder.button(
                text=dt.strftime("%d.%m.%Y"),
                callback_data=f"book_date:{ts}",
            )
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(2)

        await state.set_state(BookingStates.choose_date)
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(BookingStates.choose_date, F.data.startswith("book_date:"))
async def chose_date(callback: CallbackQuery, state: FSMContext):
    """User chose date, show times."""
    ts = int(callback.data.split(":")[1])
    date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    data = await state.get_data()
    staff_id = data.get("staff_id")
    service_id = data.get("service_id")

    await state.update_data(booking_date=date_str, booking_ts=ts)
    await callback.answer()

    try:
        times = await yclients.get_available_times(staff_id, date_str, service_id)
        if not times:
            await callback.message.edit_text(
                "Нет свободного времени в этот день. Выберите другую дату."
            )
            return

        await state.update_data(available_times=times)
        builder = InlineKeyboardBuilder()
        for i, t in enumerate(times[:20]):
            if isinstance(t, dict):
                tid = t.get("id") or t.get("datetime", "")
                dt_str = t.get("datetime", "")
                if isinstance(dt_str, str) and "T" in dt_str:
                    try:
                        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        label = dt.strftime("%H:%M")
                    except Exception:
                        label = str(dt_str)[:16]
                else:
                    label = str(tid)[:10]
                builder.button(text=label, callback_data=f"book_time:{i}")
            else:
                builder.button(text=str(t), callback_data=f"book_time:{i}")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(3)

        await state.set_state(BookingStates.choose_time)
        await callback.message.edit_text(
            "Выберите время:",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(BookingStates.choose_time, F.data.startswith("book_time:"))
async def chose_time(callback: CallbackQuery, state: FSMContext):
    """User chose time, ask for name."""
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    times = data.get("available_times", [])
    if idx < 0 or idx >= len(times):
        await callback.answer("Время недоступно. Выберите другое.", show_alert=True)
        return

    t = times[idx]
    if isinstance(t, dict):
        booking_id = str(t.get("id", ""))
        datetime_str = t.get("datetime", "")
        if not datetime_str:
            date_str = data.get("booking_date", "")
            datetime_str = f"{date_str}T09:00:00+03:00"
    else:
        date_str = data.get("booking_date", "")
        booking_id = str(t)
        datetime_str = f"{date_str}T09:00:00+03:00"

    if not datetime_str.endswith(("+00:00", "+03:00", "Z")) and "+" not in datetime_str:
        datetime_str = f"{datetime_str}+03:00"

    await state.update_data(booking_id=booking_id, booking_datetime=datetime_str)
    await state.set_state(BookingStates.enter_name)
    await callback.answer()
    await callback.message.edit_text("Введите ваше имя (ФИО):")


@router.message(BookingStates.enter_name, F.text)
async def enter_name(message: Message, state: FSMContext):
    """Save name, ask for phone."""
    await state.update_data(fullname=message.text.strip())
    await state.set_state(BookingStates.enter_phone)
    await message.answer("Введите номер телефона (например, +79001234567):")


@router.message(BookingStates.enter_phone, F.text)
async def enter_phone(message: Message, state: FSMContext):
    """Save phone, ask for email."""
    await state.update_data(phone=message.text.strip())
    await state.set_state(BookingStates.enter_email)
    await message.answer("Введите email (или /skip чтобы пропустить):")


@router.message(BookingStates.enter_email, F.text)
async def enter_email(message: Message, state: FSMContext):
    """Save email and confirm."""
    if message.text and message.text.strip().lower() != "/skip":
        await state.update_data(email=message.text.strip())
    else:
        await state.update_data(email="")
    await state.set_state(BookingStates.confirm)
    await show_confirm(message, state)


async def show_confirm(message: Message, state: FSMContext):
    """Show booking summary for confirmation."""
    data = await state.get_data()
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить запись", callback_data="book_confirm")
    builder.button(text="❌ Отмена", callback_data="menu:main")
    builder.adjust(1)

    dt_str = data.get("booking_datetime", "")
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        dt_display = dt.strftime("%d.%m.%Y в %H:%M")
    except Exception:
        dt_display = dt_str

    text = (
        f"*Проверьте данные:*\n\n"
        f"👤 Имя: {data.get('fullname')}\n"
        f"📱 Телефон: {data.get('phone')}\n"
        f"📧 Email: {data.get('email') or '—'}\n"
        f"📅 Дата и время: {dt_display}\n\n"
        f"Подтвердить запись?"
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")


@router.callback_query(BookingStates.confirm, F.data == "book_confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Create booking in YClients."""
    data = await state.get_data()
    await callback.answer()

    fullname = data.get("fullname", "")
    phone = data.get("phone", "")
    email = data.get("email", "") or "noreply@pilates.local"
    service_id = data.get("service_id")
    staff_id = data.get("staff_id")
    booking_id = data.get("booking_id")
    datetime_str = data.get("booking_datetime")

    if not all([fullname, phone, service_id, staff_id, booking_id, datetime_str]):
        await callback.message.answer("Ошибка: неполные данные. Начните запись заново.")
        await state.clear()
        return

    try:
        success, msg = await yclients.create_booking(
            fullname=fullname,
            phone=phone,
            email=email,
            service_id=service_id,
            staff_id=staff_id,
            booking_id=str(booking_id),
            datetime_str=datetime_str,
        )
        await state.clear()

        if success:
            await callback.message.edit_text(
                f"✅ {msg}\n\n"
                f"Ждём вас на занятии! 🙏"
            )
        else:
            await callback.message.edit_text(
                f"❌ Не удалось создать запись:\n{msg}\n\n"
                f"Попробуйте снова или свяжитесь с нами."
            )
    except Exception as e:
        await state.clear()
        await callback.message.edit_text(f"Ошибка при создании записи: {e}")
