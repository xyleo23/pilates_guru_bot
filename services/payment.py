"""YooKassa payment service."""
import logging
import uuid
import aiohttp
import base64
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY

BASE_URL = "https://api.yookassa.ru/v3"


def _auth_header() -> str:
    creds = f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


async def create_payment(
    amount: float,
    description: str,
    metadata: dict,
    return_url: str = "https://t.me/pilates_guru_bot",
) -> dict | None:
    """
    Создать платёж ЮКасса.
    Возвращает {"id": ..., "confirmation_url": ...} или None при ошибке.
    """
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
    }
    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Idempotence-Key": idempotence_key,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/payments",
                json=payload,
                headers=headers,
            ) as resp:
                data = await resp.json()
                if resp.status == 200:
                    url = data.get("confirmation", {}).get("confirmation_url")
                    return {"id": data["id"], "confirmation_url": url}
                logging.error(f"YooKassa error: {data}")
                return None
    except Exception as e:
        logging.error(f"YooKassa exception: {e}")
        return None


async def check_payment(payment_id: str) -> str:
    """
    Проверить статус платежа.
    Вернуть: "succeeded" | "pending" | "canceled" | "error"
    """
    headers = {"Authorization": _auth_header()}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/payments/{payment_id}",
                headers=headers,
            ) as resp:
                data = await resp.json()
                return data.get("status", "error")
    except Exception:
        return "error"
