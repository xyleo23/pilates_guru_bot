"""Booking handler - record a class via YClients."""
from datetime import datetime
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.yclients import YClientsNotConfigured, YClientsService
from services.payment import create_payment, check_payment
from config import YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
from data.studio_info import PRICES, STUDIO, TRAINERS, TRAINERS_INFO

UNAVAILABLE_MSG = f"Онлайн-запись временно недоступна. Позвоните нам: {STUDIO['phone']}"

router = Router(name="booking")

yclients = YClientsService(
    YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, str(YCLIENTS_COMPANY_ID)
)


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
    payment = State()


async def _show_booking_services(msg_or_cb, state: FSMContext, *, from_callback: bool):
    """Общая логика показа услуг — для callback и message."""
    data = await state.get_data()
    preferred_trainer = data.get("preferred_trainer")
    await state.clear()
    if preferred_trainer:
        await state.update_data(preferred_trainer=preferred_trainer)

    try:
        services = await yclients.get_services()
        if not services:
            idx = 1
            for category in PRICES.values():
                for item in category:
                    services.append({
                        "id": idx,
                        "title": item["name"],
                        "price": item.get("price", ""),
                    })
                    idx += 1
        if not services:
            text = (
                "К сожалению, сейчас нет доступных услуг для записи. "
                "Попробуйте позже или свяжитесь с нами."
            )
            if from_callback:
                await msg_or_cb.message.answer(text)
            else:
                await msg_or_cb.answer(text)
            return

        builder = InlineKeyboardBuilder()
        for s in services[:15]:
            if not isinstance(s, dict):
                continue
            sid = s.get("id") or s.get("api_id")
            title = (s.get("title") or s.get("booking_title") or "Услуга")[:40]
            builder.button(text=title, callback_data=f"book_svc:{sid}")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(1)

        await state.update_data(services=services)
        await state.set_state(BookingStates.choose_service)
        text = "Выберите тип занятия:"
        if from_callback:
            await msg_or_cb.message.edit_text(text, reply_markup=builder.as_markup())
        else:
            await msg_or_cb.answer(text, reply_markup=builder.as_markup())
    except YClientsNotConfigured:
        err = UNAVAILABLE_MSG
        if from_callback:
            await msg_or_cb.message.answer(err)
        else:
            await msg_or_cb.answer(err)
    except Exception as e:
        err = f"Ошибка при загрузке услуг: {e}"
        if from_callback:
            await msg_or_cb.message.answer(err)
        else:
            await msg_or_cb.answer(err)


@router.message(F.text == "📅 Записаться")
async def start_booking_from_message(message: Message, state: FSMContext):
    """Старт бронирования по кнопке Reply-клавиатуры."""
    await _show_booking_services(message, state, from_callback=False)


@router.callback_query(F.data == "menu:booking")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    """Start booking flow."""
    await callback.answer()
    await _show_booking_services(callback, state, from_callback=True)


@router.callback_query(BookingStates.choose_staff, F.data == "book_back:service")
async def book_back_to_service(callback: CallbackQuery, state: FSMContext):
    """Назад от выбора сотрудника к выбору услуги."""
    data = await state.get_data()
    services = data.get("services", [])
    if not services:
        await callback.answer("Начните запись заново.", show_alert=True)
        return
    await state.set_state(BookingStates.choose_service)
    builder = InlineKeyboardBuilder()
    for s in services[:15]:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or s.get("api_id")
        title = (s.get("title") or s.get("booking_title") or "Услуга")[:40]
        builder.button(text=title, callback_data=f"book_svc:{sid}")
    builder.button(text="❌ Отмена", callback_data="menu:main")
    builder.adjust(1)
    await callback.message.edit_text(
        "Выберите тип занятия:",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(BookingStates.choose_service, F.data.startswith("book_svc:"))
async def chose_service(callback: CallbackQuery, state: FSMContext):
    """User chose service, show staff."""
    service_id = int(callback.data.split(":")[1])
    await state.update_data(service_id=service_id)
    await callback.answer()

    try:
        staff = await yclients.get_staff(service_id=service_id)
        staff = [s for s in staff if s.get("bookable", True)]
        for s in staff:
            name = s.get("name", "")
            info = TRAINERS_INFO.get(name, {})
            s["best_for"] = info.get("best_for", "")
            s["experience"] = info.get("experience", "")
        if not staff:
            staff = [{"id": i + 1, "name": name} for i, name in enumerate(TRAINERS)]
        if not staff:
            await callback.message.edit_text(
                "Нет доступных инструкторов для этой услуги. Выберите другую услугу."
            )
            await start_booking(callback, state)
            return

        data = await state.get_data()
        preferred_trainer = data.get("preferred_trainer")

        def _norm(s: str) -> str:
            return (s or "").strip().casefold().replace("ё", "е")

        if preferred_trainer:
            preferred_list = [
                s for s in staff
                if _norm(s.get("name", "")) == _norm(preferred_trainer)
            ]
            other_list = [
                s for s in staff
                if _norm(s.get("name", "")) != _norm(preferred_trainer)
            ]
            staff = preferred_list + other_list

        builder = InlineKeyboardBuilder()
        for s in staff[:10]:
            sid = s.get("id")
            name = (s.get("name") or "Инструктор")[:35]
            is_recommended = (
                preferred_trainer
                and _norm(s.get("name", "")) == _norm(preferred_trainer)
            )
            prefix = "⭐ Рекомендуем " if is_recommended else ""
            desc = s.get("best_for") or s.get("experience") or ""
            label = prefix + f"{name}" + (f" — {desc[:25]}…" if len(desc) > 25 else f" — {desc}" if desc else "")
            builder.button(text=label[:60], callback_data=f"book_staff:{sid}")
        builder.button(text="⬅️ Назад", callback_data="book_back:service")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(1)

        await state.set_state(BookingStates.choose_staff)
        await callback.message.edit_text(
            "Выберите инструктора:",
            reply_markup=builder.as_markup(),
        )
    except YClientsNotConfigured:
        await callback.message.answer(UNAVAILABLE_MSG)
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(BookingStates.choose_date, F.data == "book_back:staff")
async def book_back_to_staff(callback: CallbackQuery, state: FSMContext):
    """Назад от выбора даты к выбору сотрудника."""
    data = await state.get_data()
    service_id = data.get("service_id")
    if not service_id:
        await callback.answer("Ошибка. Начните запись заново.", show_alert=True)
        return
    await callback.answer()
    # Имитируем возврат: показываем выбор сотрудника
    await state.set_state(BookingStates.choose_staff)
    try:
        staff = await yclients.get_staff(service_id=service_id)
        staff = [s for s in staff if s.get("bookable", True)]
        for s in staff:
            name = s.get("name", "")
            info = TRAINERS_INFO.get(name, {})
            s["best_for"] = info.get("best_for", "")
            s["experience"] = info.get("experience", "")
        if not staff:
            staff = [{"id": i + 1, "name": name} for i, name in enumerate(TRAINERS)]
        preferred_trainer = data.get("preferred_trainer")

        def _norm(s: str) -> str:
            return (s or "").strip().casefold().replace("ё", "е")

        if preferred_trainer:
            preferred_list = [s for s in staff if _norm(s.get("name", "")) == _norm(preferred_trainer)]
            other_list = [s for s in staff if _norm(s.get("name", "")) != _norm(preferred_trainer)]
            staff = preferred_list + other_list

        builder = InlineKeyboardBuilder()
        for s in staff[:10]:
            sid = s.get("id")
            name = (s.get("name") or "Инструктор")[:35]
            is_recommended = preferred_trainer and _norm(s.get("name", "")) == _norm(preferred_trainer)
            prefix = "⭐ Рекомендуем " if is_recommended else ""
            desc = s.get("best_for") or s.get("experience") or ""
            label = prefix + f"{name}" + (f" — {desc[:25]}…" if len(desc) > 25 else f" — {desc}" if desc else "")
            builder.button(text=label[:60], callback_data=f"book_staff:{sid}")
        builder.button(text="⬅️ Назад", callback_data="book_back:service")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(1)
        await callback.message.edit_text("Выберите инструктора:", reply_markup=builder.as_markup())
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
        dates = await yclients.get_available_dates(staff_id, service_id)
        if not dates:
            await callback.message.edit_text(
                "Нет свободных дат. Попробуйте другого инструктора."
            )
            return

        builder = InlineKeyboardBuilder()
        for date_str in dates[:14]:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                label = dt.strftime("%d.%m.%Y")
            except (ValueError, TypeError):
                label = date_str
            builder.button(
                text=label,
                callback_data=f"book_date:{date_str}",
            )
        builder.button(text="⬅️ Назад", callback_data="book_back:staff")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(2)

        await state.set_state(BookingStates.choose_date)
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=builder.as_markup(),
        )
    except YClientsNotConfigured:
        await callback.message.answer(UNAVAILABLE_MSG)
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(BookingStates.choose_time, F.data == "book_back:date")
async def book_back_to_date(callback: CallbackQuery, state: FSMContext):
    """Назад от выбора времени к выбору даты."""
    data = await state.get_data()
    staff_id = data.get("staff_id")
    service_id = data.get("service_id")
    if not staff_id or not service_id:
        await callback.answer("Ошибка. Начните запись заново.", show_alert=True)
        return
    await callback.answer()
    try:
        dates = await yclients.get_available_dates(staff_id, service_id)
        if not dates:
            await callback.message.edit_text("Нет свободных дат.")
            return
        await state.set_state(BookingStates.choose_date)
        builder = InlineKeyboardBuilder()
        for date_str in dates[:14]:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                label = dt.strftime("%d.%m.%Y")
            except (ValueError, TypeError):
                label = date_str
            builder.button(text=label, callback_data=f"book_date:{date_str}")
        builder.button(text="⬅️ Назад", callback_data="book_back:staff")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(2)
        await callback.message.edit_text("Выберите дату:", reply_markup=builder.as_markup())
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


@router.callback_query(BookingStates.choose_date, F.data.startswith("book_date:"))
async def chose_date(callback: CallbackQuery, state: FSMContext):
    """User chose date, show times."""
    raw = callback.data.split(":", 1)[1]
    try:
        ts = int(raw)
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        date_str = raw  # уже YYYY-MM-DD
    data = await state.get_data()
    staff_id = data.get("staff_id")
    service_id = data.get("service_id")

    await state.update_data(booking_date=date_str)
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
                dt_str = t.get("datetime", "") or t.get("time", "")
                if isinstance(dt_str, str):
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M"):
                        try:
                            dt = datetime.strptime(dt_str.replace("Z", "")[:19], fmt)
                            label = dt.strftime("%H:%M")
                            break
                        except (ValueError, TypeError):
                            continue
                    else:
                        label = str(dt_str)[:8]
                else:
                    label = str(t.get("time", ""))[:8]
                builder.button(text=label, callback_data=f"book_time:{i}")
            else:
                builder.button(text=str(t), callback_data=f"book_time:{i}")
        builder.button(text="⬅️ Назад", callback_data="book_back:date")
        builder.button(text="❌ Отмена", callback_data="menu:main")
        builder.adjust(3)

        await state.set_state(BookingStates.choose_time)
        await callback.message.edit_text(
            "Выберите время:",
            reply_markup=builder.as_markup(),
        )
    except YClientsNotConfigured:
        await callback.message.answer(UNAVAILABLE_MSG)
    except Exception as e:
        await callback.message.answer(f"Ошибка: {e}")


def _to_yclients_datetime(s: str, date_str: str = "") -> str:
    """Привести к формату YClients: YYYY-MM-DD HH:MM:SS."""
    if not s:
        return f"{date_str} 09:00:00" if date_str else ""
    s = str(s).replace("Z", "").replace("+00:00", "").replace("+03:00", "").strip()
    if "T" in s:
        s = s.replace("T", " ")[:19]
    if len(s) == 10 and date_str:
        return f"{date_str} 09:00:00"
    return s[:19] if len(s) >= 19 else s


@router.callback_query(BookingStates.confirm, F.data == "book_back:time")
async def book_back_to_time(callback: CallbackQuery, state: FSMContext):
    """Назад от подтверждения к выбору времени."""
    data = await state.get_data()
    times = data.get("available_times", [])
    if not times:
        await callback.answer("Ошибка. Начните запись заново.", show_alert=True)
        return
    await state.set_state(BookingStates.choose_time)
    await callback.answer()
    builder = InlineKeyboardBuilder()
    for i, t in enumerate(times[:20]):
        if isinstance(t, dict):
            dt_str = t.get("datetime", "") or t.get("time", "")
            if isinstance(dt_str, str):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M"):
                    try:
                        dt = datetime.strptime(dt_str.replace("Z", "")[:19], fmt)
                        label = dt.strftime("%H:%M")
                        break
                    except (ValueError, TypeError):
                        continue
                else:
                    label = str(dt_str)[:8]
            else:
                label = str(t.get("time", ""))[:8]
            builder.button(text=label, callback_data=f"book_time:{i}")
        else:
            builder.button(text=str(t), callback_data=f"book_time:{i}")
    builder.button(text="⬅️ Назад", callback_data="book_back:date")
    builder.button(text="❌ Отмена", callback_data="menu:main")
    builder.adjust(3)
    await callback.message.edit_text("Выберите время:", reply_markup=builder.as_markup())


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
    date_str = data.get("booking_date", "")
    if isinstance(t, dict):
        datetime_str = _to_yclients_datetime(
            t.get("datetime", "") or t.get("time", ""), date_str
        )
    else:
        datetime_str = f"{date_str} 09:00:00"
    if not datetime_str:
        datetime_str = f"{date_str} 09:00:00"

    await state.update_data(booking_datetime=datetime_str)
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
    builder.button(text="⬅️ Назад", callback_data="book_back:time")
    builder.button(text="❌ Отмена", callback_data="menu:main")
    builder.adjust(1)

    dt_str = str(data.get("booking_datetime", ""))[:19].replace("T", " ")
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        dt_display = dt.strftime("%d.%m.%Y в %H:%M")
    except (ValueError, TypeError):
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


def _flatten_services(services: list) -> list:
    """Flatten nested lists into a single flat list (e.g. [[...], [...]] -> [...])."""
    flat = []
    for item in services or []:
        if isinstance(item, list):
            flat.extend(_flatten_services(item))
        else:
            flat.append(item)
    return flat


def _get_service_amount(services: list, service_id: int) -> float:
    """Извлечь цену услуги из списка услуг."""
    flat = _flatten_services(services)
    for s in flat:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or s.get("api_id")
        if sid == service_id:
            p = s.get("price")
            if p is None:
                return 0.0
            if isinstance(p, (int, float)):
                return float(p)
            s_clean = str(p).replace(" ", "").replace("₽", "").strip()
            try:
                return float("".join(c for c in s_clean if c.isdigit() or c == "."))
            except ValueError:
                return 0.0
    return 0.0


def _get_service_title(services: list, service_id: int) -> str:
    """Название услуги для описания платежа."""
    flat = _flatten_services(services)
    for s in flat:
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or s.get("api_id")
        if sid == service_id:
            return (s.get("title") or s.get("name") or "Занятие")[:100]
    return "Занятие Pilates Guru"


@router.callback_query(BookingStates.confirm, F.data == "book_confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """Создать платёж и показать шаг оплаты."""
    data = await state.get_data()
    await callback.answer()

    fullname = data.get("fullname", "")
    phone = data.get("phone", "")
    email = data.get("email", "") or "noreply@pilates.local"
    service_id = data.get("service_id")
    staff_id = data.get("staff_id")
    datetime_str = data.get("booking_datetime")
    services = data.get("services", [])

    if not all([fullname, phone, service_id, staff_id, datetime_str]):
        await callback.message.answer("Ошибка: неполные данные. Начните запись заново.")
        await state.clear()
        return

    amount = _get_service_amount(services, service_id)
    if amount <= 0:
        await callback.message.answer(
            "Не удалось определить стоимость. Позвоните нам для записи: "
            f"{STUDIO['phone']}"
        )
        await state.clear()
        return

    description = _get_service_title(services, service_id)
    user_id = callback.from_user.id if callback.from_user else 0
    metadata = {
        "service_id": str(service_id),
        "staff_id": str(staff_id),
        "datetime": datetime_str,
        "tg_user_id": str(user_id),
    }

    payment = await create_payment(
        amount=amount,
        description=description,
        metadata=metadata,
    )

    if not payment:
        await callback.message.edit_text(
            "Ошибка при создании платежа. Позвоните нам: " + STUDIO["phone"]
        )
        await state.clear()
        return

    payment_id = payment["id"]
    confirmation_url = payment["confirmation_url"]
    await state.update_data(payment_id=payment_id)
    await state.set_state(BookingStates.payment)

    builder = InlineKeyboardBuilder()
    builder.button(text=f"💳 Оплатить {int(amount)} ₽", url=confirmation_url)
    builder.button(
        text="🔄 Проверить оплату",
        callback_data=f"check_payment:{payment_id}",
    )
    builder.button(text="❌ Отменить", callback_data="menu:main")
    builder.adjust(1)

    await callback.message.edit_text(
        f"Оплатите *{int(amount)} ₽* для подтверждения записи.\n\n"
        "Нажмите кнопку ниже для перехода к оплате.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )


@router.callback_query(BookingStates.payment, F.data.startswith("check_payment:"))
async def handle_check_payment(callback: CallbackQuery, state: FSMContext):
    """Проверить статус платежа и при успехе создать запись."""
    payment_id = callback.data.split(":", 1)[1]
    await callback.answer()

    status = await check_payment(payment_id)

    if status == "succeeded":
        data = await state.get_data()
        fullname = data.get("fullname", "")
        phone = data.get("phone", "")
        email = data.get("email", "") or "noreply@pilates.local"
        service_id = data.get("service_id")
        staff_id = data.get("staff_id")
        datetime_str = data.get("booking_datetime")

        try:
            success, msg, record_id = await yclients.create_booking(
                fullname=fullname,
                phone=phone,
                email=email,
                service_id=service_id,
                staff_id=staff_id,
                datetime_str=datetime_str,
            )
            await state.clear()
            if success:
                await callback.message.edit_text(
                    f"✅ {msg}\n\nЖдём вас на занятии! 🙏"
                )
            else:
                await callback.message.edit_text(
                    f"Оплата прошла, но запись не создана: {msg}\n"
                    f"Позвоните нам: {STUDIO['phone']}"
                )
        except YClientsNotConfigured:
            await state.clear()
            await callback.message.edit_text(UNAVAILABLE_MSG)
        except Exception as e:
            await state.clear()
            await callback.message.edit_text(
                f"Ошибка при создании записи: {e}\n"
                f"Позвоните нам: {STUDIO['phone']}"
            )

    elif status == "pending":
        await callback.answer(
            "Оплата ещё не прошла. Попробуйте через минуту.",
            show_alert=True,
        )

    elif status == "canceled":
        await state.clear()
        await callback.message.edit_text(
            "Платёж отменён. Начните запись заново."
        )

    else:
        await callback.message.edit_text(
            f"Ошибка проверки. Позвоните нам: {STUDIO['phone']}"
        )


