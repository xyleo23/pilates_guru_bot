"""Manage booking: cancel or reschedule records."""
from datetime import datetime

import pytz
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
from data.studio_info import STUDIO
from services.yclients import YClientsNotConfigured, YClientsService

MSK = pytz.timezone("Europe/Moscow")
UNAVAILABLE_MSG = f"Онлайн-запись временно недоступна. Позвоните нам: {STUDIO['phone']}"

router = Router(name="manage_booking")
yclients = YClientsService(
    YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, str(YCLIENTS_COMPANY_ID)
)


class ManageStates(StatesGroup):
    choose_action = State()
    choose_record = State()
    confirm_cancel = State()
    choose_new_date = State()
    choose_new_time = State()
    confirm_reschedule = State()


def _parse_record_datetime(record: dict) -> datetime | None:
    """Parse record datetime to MSK-aware datetime."""
    dt_val = record.get("datetime") or record.get("date") or record.get("visit_start")
    if not dt_val:
        return None
    if isinstance(dt_val, (int, float)):
        return datetime.fromtimestamp(dt_val, tz=MSK)
    s = str(dt_val).replace("Z", "").replace("+00:00", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s[:19], fmt[:19].replace("%z", ""))
            if dt.tzinfo is None:
                dt = MSK.localize(dt)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def _format_record_label(record: dict) -> str:
    """Format record for button: '{date} {time} — {trainer} ({service})'."""
    dt = _parse_record_datetime(record)
    date_str = dt.strftime("%d.%m") if dt else "?"
    time_str = dt.strftime("%H:%M") if dt else "?"

    staff = record.get("staff") or {}
    trainer = staff.get("name") if isinstance(staff, dict) else str(staff)
    if not trainer:
        trainer = record.get("staff_name", "Тренер")

    services = record.get("services") or []
    svc = (services[0] if services else {})
    service_title = svc.get("title") or svc.get("booking_title", "Занятие") if isinstance(svc, dict) else "Занятие"

    return f"{date_str} {time_str} — {trainer} ({service_title})"


def _get_main_menu_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="Главное меню", callback_data="menu:main")
    return builder.as_markup()


@router.callback_query(F.data == "menu:my_records")
async def show_my_records(callback: CallbackQuery, state: FSMContext):
    """Handler for menu:my_records — show client's records."""
    data = await state.get_data()
    phone = data.get("client_phone")
    await callback.answer()

    if not phone:
        await callback.message.edit_text(
            "Для просмотра записей укажите телефон. Отправьте /start.",
            reply_markup=_get_main_menu_button(),
        )
        return

    try:
        records = await yclients.get_client_records(phone)
    except YClientsNotConfigured:
        await callback.message.edit_text(UNAVAILABLE_MSG, reply_markup=_get_main_menu_button())
        return
    except Exception as e:
        await callback.message.edit_text(
            f"Ошибка загрузки записей: {e}",
            reply_markup=_get_main_menu_button(),
        )
        return

    if not records:
        await callback.message.edit_text(
            "У вас нет предстоящих записей",
            reply_markup=_get_main_menu_button(),
        )
        return

    builder = InlineKeyboardBuilder()
    for r in records:
        rid = r.get("id")
        if rid is None:
            continue
        label = _format_record_label(r)[:64]
        builder.button(text=label, callback_data=f"manage:{rid}")
    builder.button(text="Главное меню", callback_data="menu:main")
    builder.adjust(1)

    await state.update_data(manage_records=records)
    await state.set_state(ManageStates.choose_record)
    await callback.message.edit_text(
        "Выберите запись для отмены или переноса:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("remind_ok:"))
async def remind_ok(callback: CallbackQuery):
    await callback.message.edit_text(
        "Отлично, ждём вас! 🙏\n"
        "Приходите за 5–10 минут, не забудьте носки."
    )
    await callback.answer()


@router.callback_query(ManageStates.choose_record, F.data.startswith("manage:"))
async def show_record_details(callback: CallbackQuery, state: FSMContext):
    """Show record details and action buttons (cancel / reschedule)."""
    record_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    records = data.get("manage_records", [])
    record = next((r for r in records if r.get("id") == record_id), None)

    await callback.answer()
    if not record:
        await callback.message.edit_text(
            "Запись не найдена.",
            reply_markup=_get_main_menu_button(),
        )
        await state.clear()
        return

    dt = _parse_record_datetime(record)
    hours_left = (
        (dt - datetime.now(MSK)).total_seconds() / 3600
        if dt
        else 999
    )

    staff = record.get("staff") or {}
    trainer = staff.get("name") if isinstance(staff, dict) else record.get("staff_name", "Тренер")
    services = record.get("services") or []
    svc = services[0] if services else {}
    service_title = svc.get("title") or svc.get("booking_title", "Занятие") if isinstance(svc, dict) else "Занятие"

    date_str = dt.strftime("%d.%m.%Y") if dt else "?"
    time_str = dt.strftime("%H:%M") if dt else "?"

    text = (
        f"📅 *Дата:* {date_str}\n"
        f"🕐 *Время:* {time_str}\n"
        f"👤 *Тренер:* {trainer}\n"
        f"📋 *Услуга:* {service_title}\n\n"
    )
    if hours_left < 20:
        text += (
            "⚠️ До тренировки менее 20 часов. При отмене/переносе "
            "возможно списание согласно правилам студии.\n\n"
        )
    text += "Выберите действие:"

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить запись", callback_data="manage_cancel:1")
    builder.button(text="🔄 Перенести запись", callback_data="manage_reschedule:1")
    builder.button(text="Главное меню", callback_data="menu:main")
    builder.adjust(1)

    staff_id = record.get("staff_id") or (staff.get("id") if isinstance(staff, dict) else None)
    service_id = svc.get("id") if isinstance(svc, dict) else record.get("service_id")
    # YClients records may nest in appointments
    if not staff_id or not service_id:
        appointments = record.get("appointments") or [record]
        app = appointments[0] if appointments else {}
        staff_id = staff_id or app.get("staff_id") or (app.get("staff") or {}).get("id")
        svcs = app.get("services") or app.get("service_ids") or []
        if svcs:
            s0 = svcs[0]
            service_id = service_id or (s0 if isinstance(s0, int) else (s0.get("id") if isinstance(s0, dict) else None))

    await state.update_data(
        manage_record_id=record_id,
        manage_record=record,
        manage_hours_left=hours_left,
        manage_staff_id=staff_id,
        manage_service_id=service_id,
    )
    await state.set_state(ManageStates.choose_action)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")


# --- Cancel flow ---

@router.callback_query(ManageStates.choose_action, F.data == "manage_cancel:1")
async def start_cancel(callback: CallbackQuery, state: FSMContext):
    """Start cancel confirmation flow."""
    data = await state.get_data()
    hours_left = data.get("manage_hours_left", 0)
    late_cancels = data.get("late_cancels", 0)
    record_id = data.get("manage_record_id")

    await callback.answer()
    await state.update_data(manage_action="cancel")
    await state.set_state(ManageStates.confirm_cancel)

    if hours_left >= 20:
        text = "Отмена бесплатна. Подтвердить отмену записи?"
    elif late_cancels == 0:
        text = "Первое нарушение — средства остаются на депозите.\n\nПодтвердить отмену?"
    else:
        text = "Повторное нарушение — средства будут списаны.\n\nПодтвердить отмену?"

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, отменить", callback_data="confirm_cancel_yes")
    builder.button(text="❌ Нет", callback_data="menu:my_records")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(ManageStates.confirm_cancel, F.data == "confirm_cancel_yes")
async def do_cancel(callback: CallbackQuery, state: FSMContext):
    """Execute cancel and show result."""
    data = await state.get_data()
    record_id = data.get("manage_record_id")
    late_cancels = data.get("late_cancels", 0)
    hours_left = data.get("manage_hours_left", 0)

    await callback.answer()
    new_late_cancels = late_cancels + 1 if (hours_left < 20 and late_cancels == 0) else late_cancels
    await state.clear()
    if new_late_cancels > 0:
        await state.update_data(
            late_cancels=new_late_cancels,
            client_phone=data.get("client_phone"),
        )

    try:
        success, msg = await yclients.cancel_record(record_id)
        if success:
            text = f"✅ {msg}\n\nЗапись успешно отменена."
        else:
            text = f"❌ Не удалось отменить: {msg}"
    except YClientsNotConfigured:
        text = UNAVAILABLE_MSG
    except Exception as e:
        text = f"Ошибка при отмене: {e}"

    await callback.message.edit_text(text, reply_markup=_get_main_menu_button())


# --- Reschedule flow ---

@router.callback_query(ManageStates.choose_action, F.data == "manage_reschedule:1")
async def start_reschedule(callback: CallbackQuery, state: FSMContext):
    """Check hours and show available dates for reschedule."""
    data = await state.get_data()
    hours_left = data.get("manage_hours_left", 0)
    staff_id = data.get("manage_staff_id")
    service_id = data.get("manage_service_id")

    await callback.answer()

    if hours_left < 20:
        await callback.message.edit_text(
            "Перенос возможен только за 20+ часов до занятия.",
            reply_markup=_get_main_menu_button(),
        )
        await state.clear()
        return

    if not staff_id or not service_id:
        await callback.message.edit_text(
            "Не удалось определить данные записи для переноса.",
            reply_markup=_get_main_menu_button(),
        )
        await state.clear()
        return

    try:
        dates = await yclients.get_available_dates(staff_id, service_id)
    except YClientsNotConfigured:
        await callback.message.edit_text(UNAVAILABLE_MSG, reply_markup=_get_main_menu_button())
        await state.clear()
        return
    except Exception as e:
        await callback.message.edit_text(
            f"Ошибка загрузки дат: {e}",
            reply_markup=_get_main_menu_button(),
        )
        await state.clear()
        return

    if not dates:
        await callback.message.edit_text(
            "Нет доступных дат для переноса.",
            reply_markup=_get_main_menu_button(),
        )
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    for d in dates[:14]:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            label = dt.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            label = d
        builder.button(text=label, callback_data=f"reschedule_date:{d}")
    builder.button(text="❌ Отмена", callback_data="menu:my_records")
    builder.adjust(2)

    await state.set_state(ManageStates.choose_new_date)
    await callback.message.edit_text(
        "Выберите новую дату для переноса:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(ManageStates.choose_new_date, F.data.startswith("reschedule_date:"))
async def chose_reschedule_date(callback: CallbackQuery, state: FSMContext):
    """Show available times for chosen date."""
    date_str = callback.data.split(":")[1]
    data = await state.get_data()
    staff_id = data.get("manage_staff_id")
    service_id = data.get("manage_service_id")

    await state.update_data(reschedule_date=date_str)
    await callback.answer()

    try:
        times = await yclients.get_available_times(staff_id, date_str, service_id)
    except YClientsNotConfigured:
        await callback.message.edit_text(UNAVAILABLE_MSG, reply_markup=_get_main_menu_button())
        await state.clear()
        return
    except Exception as e:
        await callback.message.edit_text(
            f"Ошибка загрузки времени: {e}",
            reply_markup=_get_main_menu_button(),
        )
        await state.clear()
        return

    if not times:
        await callback.message.edit_text(
            "Нет свободного времени в этот день. Выберите другую дату.",
            reply_markup=_get_main_menu_button(),
        )
        return

    builder = InlineKeyboardBuilder()
    for i, t in enumerate(times[:20]):
        if isinstance(t, dict):
            dt_str = t.get("datetime") or t.get("time", "")
            if isinstance(dt_str, str):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M"):
                    try:
                        dt = datetime.strptime(str(dt_str).replace("Z", "")[:19], fmt)
                        label = dt.strftime("%H:%M")
                        break
                    except (ValueError, TypeError):
                        continue
                else:
                    label = str(dt_str)[:8]
            else:
                label = str(t.get("time", ""))[:8]
            builder.button(text=label, callback_data=f"reschedule_time:{i}")
        else:
            builder.button(text=str(t), callback_data=f"reschedule_time:{i}")
    builder.button(text="❌ Отмена", callback_data="menu:my_records")
    builder.adjust(3)

    await state.update_data(reschedule_times=times)
    await state.set_state(ManageStates.choose_new_time)
    await callback.message.edit_text(
        "Выберите время:",
        reply_markup=builder.as_markup(),
    )


def _to_datetime_str(t: dict, date_str: str) -> str:
    """Convert slot to YClients datetime string."""
    dt_val = t.get("datetime") or t.get("time", "")
    if isinstance(dt_val, str):
        s = dt_val.replace("Z", "").replace("T", " ")[:19]
        if len(s) >= 19:
            return s
        return f"{date_str} {s}" if s else f"{date_str} 09:00:00"
    return f"{date_str} 09:00:00"


@router.callback_query(ManageStates.choose_new_time, F.data.startswith("reschedule_time:"))
async def chose_reschedule_time(callback: CallbackQuery, state: FSMContext):
    """Show confirmation for reschedule."""
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    times = data.get("reschedule_times", [])
    date_str = data.get("reschedule_date", "")

    if idx < 0 or idx >= len(times):
        await callback.answer("Время недоступно.", show_alert=True)
        return

    t = times[idx]
    new_datetime_str = _to_datetime_str(t, date_str) if isinstance(t, dict) else f"{date_str} 09:00:00"

    await state.update_data(reschedule_datetime=new_datetime_str)
    await state.set_state(ManageStates.confirm_reschedule)
    await callback.answer()

    record = data.get("manage_record", {})
    staff = record.get("staff") or {}
    trainer = staff.get("name") if isinstance(staff, dict) else "Тренер"
    services = record.get("services") or []
    svc = services[0] if services else {}
    service_title = svc.get("title") or "Занятие" if isinstance(svc, dict) else "Занятие"

    try:
        dt = datetime.strptime(new_datetime_str, "%Y-%m-%d %H:%M:%S")
        display = dt.strftime("%d.%m.%Y в %H:%M")
    except (ValueError, TypeError):
        display = new_datetime_str

    text = (
        f"Перенос на:\n\n"
        f"📅 Дата: {display}\n"
        f"👤 Тренер: {trainer}\n"
        f"📋 Услуга: {service_title}\n\n"
        f"Подтвердить перенос?"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, перенести", callback_data="confirm_reschedule_yes")
    builder.button(text="❌ Отмена", callback_data="menu:my_records")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(ManageStates.confirm_reschedule, F.data == "confirm_reschedule_yes")
async def do_reschedule(callback: CallbackQuery, state: FSMContext):
    """Execute reschedule and show result."""
    data = await state.get_data()
    record_id = data.get("manage_record_id")
    staff_id = data.get("manage_staff_id")
    service_id = data.get("manage_service_id")
    new_datetime_str = data.get("reschedule_datetime")

    await callback.answer()
    await state.clear()

    if not all([record_id, staff_id, service_id, new_datetime_str]):
        await callback.message.edit_text(
            "Ошибка: неполные данные. Попробуйте снова.",
            reply_markup=_get_main_menu_button(),
        )
        return

    try:
        success, msg = await yclients.reschedule_record(
            record_id, staff_id, service_id, new_datetime_str
        )
        if success:
            text = f"✅ {msg}\n\nЗапись перенесена."
        else:
            text = f"❌ Не удалось перенести: {msg}"
    except YClientsNotConfigured:
        text = UNAVAILABLE_MSG
    except Exception as e:
        text = f"Ошибка при переносе: {e}"

    await callback.message.edit_text(text, reply_markup=_get_main_menu_button())
