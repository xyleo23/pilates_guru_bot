"""Configuration for Pilates Guru Telegram Bot."""
import os
from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str) -> str:
    """Get required environment variable."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


BOT_TOKEN = _get_env("BOT_TOKEN")
YCLIENTS_TOKEN = _get_env("YCLIENTS_TOKEN")
YCLIENTS_USER_TOKEN = os.getenv("YCLIENTS_USER_TOKEN", "")
YCLIENTS_COMPANY_ID = os.getenv("YCLIENTS_COMPANY_ID", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ADMIN_TG_ID = int(_get_env("ADMIN_TG_ID"))
