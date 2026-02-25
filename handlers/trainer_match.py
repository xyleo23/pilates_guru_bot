"""Trainer matching handler — 3 questions → AI recommends trainer."""
import json
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.studio_info import STUDIO

router = Router(name="match")


class MatchStates(StatesGroup):
    q1_goal = State()
    q2_level = State()
    q3_health = State()
    result = State()


async def match_trainer_ai(goal: str, level: str, health: str) -> dict:
    """Call OpenAI to recommend a trainer based on user answers."""
    from openai import AsyncOpenAI
    from config import OPENAI_API_KEY

    if not OPENAI_API_KEY:
        return {
            "trainer": "Марина",
            "reason": "Марина поможет подобрать программу на первом занятии.",
            "first_step": "Запишитесь на Стартовую персональную (2 400 ₽)",
            "escalate": False,
        }

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    prompt = f"""
Ты — ассистент студии пилатеса Pilates Guru.
Тренеры студии:
- Тамара: опыт с 2008г, силовые тренировки, реабилитация колен/таза/позвоночника
- Дарья: с 2018г, реабилитация после травм/операций, нейрореабилитация
- Марина: мягкий подход, идеально для новичков
- Мария: классический пилатес, интенсивные тренировки, структурированный подход

Клиент:
- Цель: {goal}
- Уровень: {level}
- Здоровье: {health}

Ответь строго в формате JSON:
{{
  "trainer": "Имя тренера",
  "reason": "1-2 предложения почему именно этот тренер",
  "first_step": "Конкретный следующий шаг (например: запишитесь на Стартовую персональную)"
}}
Если клиент указал травму или беременность — рекомендуй Дарью и добавь:
"escalate": true
"""
    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logging.error(f"match_trainer_ai error: {e}")
        return {
            "trainer": "Марина",
            "reason": "Марина поможет подобрать программу на первом занятии.",
            "first_step": "Запишитесь на Стартовую персональную (2 400 ₽)",
            "escalate": False,
        }


# Goal labels for display in prompt
GOAL_LABELS = {
    "strength": "укрепить тело и мышцы",
    "flexibility": "гибкость и осанка",
    "rehab": "реабилитация после травмы",
    "newbie": "первый раз, хочу попробовать",
}
LEVEL_LABELS = {
    "none": "никогда не занимался(ась)",
    "beginner": "немного занимался(ась)",
    "regular": "занимаюсь регулярно",
}
HEALTH_LABELS = {
    "none": "всё в порядке",
    "spine": "проблемы со спиной/суставами",
    "injury": "травма или операция",
    "pregnancy": "беременность / послеродовой",
}


@router.callback_query(F.data == "menu:match_trainer")
async def start_match(callback: CallbackQuery, state: FSMContext):
    """Start trainer matching flow."""
    await state.clear()
    await state.set_state(MatchStates.q1_goal)
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.button(text="💪 Укрепить тело и мышцы", callback_data="q1:strength")
    builder.button(text="🧘 Гибкость и осанка", callback_data="q1:flexibility")
    builder.button(text="🩹 Реабилитация после травмы", callback_data="q1:rehab")
    builder.button(text="🌱 Первый раз, хочу попробовать", callback_data="q1:newbie")
    builder.adjust(1)

    await callback.message.edit_text(
        "Ответьте на 3 коротких вопроса — я подберу тренера под ваши цели 🙏",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(MatchStates.q1_goal, F.data.startswith("q1:"))
async def answer_q1(callback: CallbackQuery, state: FSMContext):
    """Save goal, show q2."""
    value = callback.data.split(":", 1)[1]
    await state.update_data(match_goal=value)
    await state.set_state(MatchStates.q2_level)
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Никогда не занимался(ась)", callback_data="q2:none")
    builder.button(text="🔰 Немного занимался(ась)", callback_data="q2:beginner")
    builder.button(text="✅ Занимаюсь регулярно", callback_data="q2:regular")
    builder.adjust(1)

    await callback.message.edit_text(
        "Какой у вас опыт занятий пилатесом?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(MatchStates.q2_level, F.data.startswith("q2:"))
async def answer_q2(callback: CallbackQuery, state: FSMContext):
    """Save level, show q3."""
    value = callback.data.split(":", 1)[1]
    await state.update_data(match_level=value)
    await state.set_state(MatchStates.q3_health)
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.button(text="❤️ Всё в порядке", callback_data="q3:none")
    builder.button(text="🦴 Проблемы со спиной/суставами", callback_data="q3:spine")
    builder.button(text="🤕 Травма или операция", callback_data="q3:injury")
    builder.button(text="🤰 Беременность / послеродовой", callback_data="q3:pregnancy")
    builder.adjust(1)

    await callback.message.edit_text(
        "Есть ли особенности здоровья?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(MatchStates.q3_health, F.data.startswith("q3:"))
async def answer_q3(callback: CallbackQuery, state: FSMContext):
    """Save health, call AI, show result."""
    value = callback.data.split(":", 1)[1]
    data = await state.get_data()
    goal = data.get("match_goal", "newbie")
    level = data.get("match_level", "none")

    goal_label = GOAL_LABELS.get(goal, goal)
    level_label = LEVEL_LABELS.get(level, level)
    health_label = HEALTH_LABELS.get(value, value)

    result = await match_trainer_ai(goal_label, level_label, health_label)
    trainer = result.get("trainer", "Марина")
    reason = result.get("reason", "")
    first_step = result.get("first_step", "Запишитесь на Стартовую персональную (2 400 ₽)")
    escalate = result.get("escalate", False)

    await state.update_data(
        match_health=value,
        preferred_trainer=trainer,
    )
    await state.set_state(MatchStates.result)
    await callback.answer()

    text = (
        f"🎯 *Ваш тренер — {trainer}*\n\n"
        f"{reason}\n\n"
        f"📌 {first_step}"
    )
    if escalate:
        telegram_handle = STUDIO["telegram"].lstrip("@")
        text += (
            "\n\n"
            "⚠️ Для записи с вашими особенностями здоровья "
            "рекомендуем предварительную консультацию с тренером."
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться", callback_data="menu:booking")
    builder.button(text="🔄 Выбрать другого тренера", callback_data="menu:match_trainer")
    builder.button(text="◀️ Главное меню", callback_data="menu:main")
    if escalate:
        builder.button(
            text="💬 Написать напрямую",
            url=f"https://t.me/{telegram_handle}",
        )
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
