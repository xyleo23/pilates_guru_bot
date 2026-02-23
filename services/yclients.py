"""YClients API service for schedule and booking."""
import aiohttp
from typing import Any


class YClientsService:
    """Service for interacting with YClients API."""

    BASE_URL = "https://api.yclients.com/api/v1"

    def __init__(self, partner_token: str, user_token: str, company_id: str):
        self.partner_token = partner_token
        self.user_token = user_token
        self.company_id = company_id
        self._headers = {
            "Accept": "application/vnd.yclients.v2+json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {partner_token}, User {user_token}",
        }

    async def get_services(self, staff_id: int | None = None, datetime_str: str | None = None) -> list[dict]:
        """Get list of available services."""
        url = f"{self.BASE_URL}/book_services/{self.company_id}"
        params = {}
        if staff_id is not None:
            params["staff_id"] = staff_id
        if datetime_str:
            params["datetime"] = datetime_str

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers, params=params or None) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    return data["data"] if isinstance(data["data"], list) else []
                return []

    async def get_staff(self, service_id: int | None = None, datetime_str: str | None = None) -> list[dict]:
        """Get list of staff/instructors."""
        url = f"{self.BASE_URL}/book_staff/{self.company_id}"
        params = {}
        if service_id is not None:
            params["service_ids[]"] = service_id
        if datetime_str:
            params["datetime"] = datetime_str

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers, params=params or None) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    return data["data"] if isinstance(data["data"], list) else []
                return []

    async def get_available_dates(
        self, staff_id: int | None = None, service_id: int | None = None
    ) -> list[int]:
        """Get available booking dates (Unix timestamps)."""
        url = f"{self.BASE_URL}/book_dates/{self.company_id}"
        params = {}
        if staff_id is not None:
            params["staff_id"] = staff_id
        if service_id is not None:
            params["service_ids[]"] = service_id

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers, params=params or None) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    return data["data"].get("booking_dates", []) or []
                return []

    async def get_available_times(
        self, staff_id: int, date: str, service_id: int | None = None
    ) -> list[dict]:
        """
        Get available time slots for a staff member on a specific date.
        date format: YYYY-MM-DD
        Returns list of seances with id, datetime, etc.
        """
        url = f"{self.BASE_URL}/book_times/{self.company_id}/{staff_id}/{date}"
        params = {}
        if service_id is not None:
            params["service_ids[]"] = service_id

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers, params=params or None) as resp:
                data = await resp.json()
                if data.get("success") and "data" in data:
                    times = data["data"]
                    return times if isinstance(times, list) else times.get("seances", [])
                return []

    async def create_booking(
        self,
        *,
        fullname: str,
        phone: str,
        email: str,
        service_id: int,
        datetime_str: str,
        staff_id: int,
        booking_id: str,
        comment: str = "",
    ) -> tuple[bool, str]:
        """
        Create a booking.
        Returns (success, message).
        datetime_str: ISO 8601 format (e.g. 2024-02-24T10:00:00+03:00)
        """
        url = f"{self.BASE_URL}/book_record/{self.company_id}"
        payload = {
            "phone": phone,
            "email": email,
            "fullname": fullname,
            "appointments": [
                {
                    "id": booking_id,
                    "services": [service_id],
                    "staff_id": staff_id,
                    "events": [],
                    "datetime": datetime_str,
                    "chargeStatus": "",
                    "comment": comment,
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self._headers, json=payload) as resp:
                data = await resp.json()
                if data.get("success"):
                    return True, "Запись успешно создана!"
                errors = data.get("errors", {})
                if isinstance(errors, dict):
                    msg = errors.get("message", str(errors))
                else:
                    msg = str(errors)
                return False, msg or "Не удалось создать запись"
