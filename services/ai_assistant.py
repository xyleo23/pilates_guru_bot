from datetime import datetime
from openai import AsyncOpenAI
from config import OPENAI_API_KEY
from data.studio_info import STUDIO, PRICES, FAQ, RULES, TRAINERS

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

def get_admin_name() -> str:
    """По чётным дням — Мария, по нечётным — Ирина"""
    day = datetime.now().day
    return "Мария" if day % 2 == 0 else "Ирина"

SYSTEM_PROMPT = """
Ты — администратор студии пилатеса Pilates Guru.
Твоё имя: {name}
Адрес: {address}, метро {metro}
График: {schedule}
Телефон: {phone}

Прайс:
- Стартовая персональная (новичок): 2400 ₽
- Персональная разовая: 4000 ₽
- Абонемент 8 персональных: 28800 ₽
- Групповая разовая: 1800 ₽
- Абонемент 8 групповых: 13600 ₽
- Сплит разовая (2 чел): 5500 ₽

Правила:
- Отмена бесплатна за 20+ часов до занятия
- Для новичков только стартовая тренировка
- Предоплата 100% обязательна

Стиль общения:
- Дружелюбно, тепло, профессионально
- Обращение на "Вы"
- Короткие ответы (2-4 предложения)
- Используй эмодзи умеренно
- Если вопрос про запись — предлагай нажать кнопку "Записаться"
- Если не знаешь ответа — предложи связаться напрямую: {phone}
- НЕ давай медицинских рекомендаций
- НЕ обещай скидки
"""

async def get_ai_response(user_message: str,
                          chat_history: list = None) -> str:
    if not OPENAI_API_KEY:
        return ("Для записи воспользуйтесь кнопкой меню, "
                "или позвоните нам: {phone}".format(**STUDIO))

    name = get_admin_name()
    system = SYSTEM_PROMPT.format(name=name, **STUDIO)

    messages = [{"role": "system", "content": system}]

    if chat_history:
        messages.extend(chat_history[-6:])  # последние 3 пары

    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return ("Сейчас не могу ответить. "
                "Позвоните нам: " + STUDIO["phone"])
