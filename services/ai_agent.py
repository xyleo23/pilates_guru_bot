"""AI Agent Marina — in-code replacement for n8n AI assistant."""
import logging
from collections import deque

from openai import AsyncOpenAI

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

# In-memory dialog history: user_id -> deque of last 10 messages ({"role": str, "content": str})
DIALOG_HISTORY: dict[int, deque[dict[str, str]]] = {}
MAX_HISTORY = 10

SYSTEM_PROMPT = """Ты администратор студии пилатеса PILATES GURU по имени Марина. 
Твоя задача — вежливо, тепло и заботливо общаться с клиентами, отвечать на их вопросы о пилатесе и студии.
КРИТИЧНЫЕ ПРАВИЛА:
1. Если клиент хочет записаться или узнать расписание — не пытайся выдумывать время. Вместо этого вежливо попроси его нажать кнопку '📅 Записаться' в меню ниже.
2. Если клиент спрашивает про цены — отвечай кратко и направляй в раздел '💰 Цены и услуги' или '📅 Записаться'.
3. Не генерируй ссылки на оплату самостоятельно.
4. Общайся коротко (1-3 предложения), с эмодзи, в дружелюбном женском стиле."""

ERROR_MESSAGE = (
    "Извините, произошла техническая ошибка. "
    "Попробуйте написать ещё раз или воспользуйтесь кнопками меню. 🙏"
)


def _get_client() -> AsyncOpenAI | None:
    """Return OpenAI client only if API key is set."""
    if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
        return None
    return AsyncOpenAI(api_key=OPENAI_API_KEY)


def _get_messages(user_id: int, user_text: str) -> list[dict[str, str]]:
    """Build messages list: system + history + current user message."""
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if user_id not in DIALOG_HISTORY:
        DIALOG_HISTORY[user_id] = deque(maxlen=MAX_HISTORY)
    history = DIALOG_HISTORY[user_id]
    messages.extend(list(history))
    messages.append({"role": "user", "content": user_text})

    return messages


def _append_to_history(user_id: int, user_text: str, assistant_text: str) -> None:
    """Append user and assistant messages to history."""
    if user_id not in DIALOG_HISTORY:
        DIALOG_HISTORY[user_id] = deque(maxlen=MAX_HISTORY)
    DIALOG_HISTORY[user_id].append({"role": "user", "content": user_text})
    DIALOG_HISTORY[user_id].append({"role": "assistant", "content": assistant_text})


NEW_CLIENT_PROMPT = """Ты Марина, администратор студии пилатеса PILATES GURU.
Клиент впервые в студии. Он ответил на вопросы:
- Цели: {goals}
- Травмы/противопоказания: {injuries}

Сгенерируй короткое (2-4 предложения) персональное приветствие. Поблагодари за ответы, отметь их цели, мягко упомяни про противопоказания (если есть), пригласи записаться на пробное занятие. Дружелюбный женский стиль, эмодзи. Не генерируй ссылки."""


async def get_new_client_welcome(
    user_id: int, goals: str, injuries: str
) -> str:
    """Generate personalized welcome for new client based on questionnaire."""
    client = _get_client()
    if not client:
        return (
            "Рады видеть вас в Pilates Guru! 🙏 "
            "Запишитесь на пробное занятие через кнопку ниже — подберём идеальный формат."
        )

    content = NEW_CLIENT_PROMPT.format(
        goals=goals or "не указано",
        injuries=injuries or "нет",
    )
    messages = [{"role": "system", "content": content}]
    messages.append({"role": "user", "content": "Сгенерируй приветствие."})

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
        return text.strip() or (
            "Рады видеть вас в Pilates Guru! 🙏 "
            "Запишитесь на пробное занятие — подберём идеальный формат."
        )
    except Exception as e:
        logger.exception("AI new client welcome error: %s", e)
        return (
            "Рады видеть вас в Pilates Guru! 🙏 "
            "Запишитесь на пробное занятие через кнопку ниже."
        )


async def get_ai_response(user_id: int, text: str) -> str:
    """
    Get AI response for the user message. Keeps last 10 messages per user for context.

    Returns the assistant's reply or a polite error message on API failure.
    """
    client = _get_client()
    if not client:
        logger.warning("OPENAI_API_KEY not set, returning fallback message")
        return (
            "Для записи и расписания воспользуйтесь кнопкой '📅 Записаться' в меню. "
            "Для цен — раздел '💰 Цены и услуги'. 🙏"
        )

    messages = _get_messages(user_id, text)

    try:
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        assistant_text = resp.choices[0].message.content or ""
        if not assistant_text.strip():
            return ERROR_MESSAGE

        _append_to_history(user_id, text, assistant_text.strip())
        return assistant_text.strip()
    except Exception as e:
        logger.exception("OpenAI API error: %s", e)
        return ERROR_MESSAGE
