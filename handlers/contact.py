"""Contact sharing handler — onboarding flow with YClients lookup."""
import logging
import re

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove

from config import YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, YCLIENTS_COMPANY_ID
from services.yclients import YClientsService, YClientsNotConfigured
from handlers.start import get_onboarding_main_keyboard
from services.ai_agent import get_new_client_welcome

router = Router(name="contact")

yclients = YClientsService(
    YCLIENTS_TOKEN, YCLIENTS_USER_TOKEN, str(YCLIENTS_COMPANY_ID)
)


class NewClientStates(StatesGroup):
    """FSM for new client questionnaire."""
    goals = State()
    injuries = State()


def _normalize_phone(phone: str) -> str:
    """Normalize phone for YClients lookup."""
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 10 and digits[0] in "789":
        return "+7" + digits
    if len(digits) == 11 and digits[0] == "7":
        return "+" + digits
    return "+" + digits if digits else ""


@router.message(F.contact)
async def on_contact_shared(message: Message, state: FSMContext):
    """Handle shared contact — lookup in YClients, existing vs new client flow."""
    if not message.contact or not message.contact.phone_number:
        await message.answer("Не удалось получить номер. Попробуйте ещё раз.")
        return

    phone = _normalize_phone(message.contact.phone_number)
    await state.update_data(phone=phone)
    await message.answer("⏳ Проверяю...", reply_markup=ReplyKeyboardRemove())

    try:
        client = await yclients.get_client_by_phone(phone)
    except YClientsNotConfigured:
        logging.warning("YClients not configured, treating as new client")
        client = None
    except Exception as e:
        logging.exception("YClients get_client_by_phone error: %s", e)
        client = None

    if client and isinstance(client, dict):
        name = (client.get("name") or client.get("fullname") or "").strip()
        display_name = name.split()[0] if name else "друг"
        await state.update_data(client_name=display_name, yclients_client=client)
        await state.clear()

        text = f"Рада вас снова видеть, {display_name}! Чем могу помочь сегодня?"
        await message.answer(
            text,
            reply_markup=get_onboarding_main_keyboard(),
        )
    else:
        await state.set_state(NewClientStates.goals)
        await message.answer(
            "Вижу, вы у нас впервые! Давайте подберём вам идеальную тренировку.\n\n"
            "Какие у вас основные цели? "
            "(Например: здоровая спина, гибкость, похудение)"
        )


@router.message(NewClientStates.goals, F.text)
async def onboarding_goals(message: Message, state: FSMContext):
    """Question 1 — goals answered, ask about injuries."""
    goals = (message.text or "").strip()[:500]
    await state.update_data(goals=goals)
    await state.set_state(NewClientStates.injuries)
    await message.answer(
        "Есть ли у вас какие-то травмы или медицинские противопоказания, "
        "о которых должен знать тренер?"
    )


@router.message(NewClientStates.injuries, F.text)
async def onboarding_injuries(message: Message, state: FSMContext):
    """Question 2 — injuries answered, AI personalized welcome + main menu."""
    injuries = (message.text or "").strip()[:500]
    await state.update_data(injuries=injuries)

    data = await state.get_data()
    goals = data.get("goals", "")
    user_id = message.from_user.id if message.from_user else 0

    welcome_text = await get_new_client_welcome(
        user_id=user_id,
        goals=goals,
        injuries=injuries,
    )

    await state.clear()
    await message.answer(
        welcome_text,
        reply_markup=get_onboarding_main_keyboard(),
    )
