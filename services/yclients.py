"""YClients API service for schedule and booking."""
import logging
from datetime import date, timedelta

import aiohttp

__all__ = ["YClientsService", "YClientsNotConfigured"]


class YClientsNotConfigured(Exception):
    """YClients API не настроен (отсутствуют токены или company_id)."""

    pass


class YClientsService:
    """Сервис для работы с YClients API."""

    def __init__(self, partner_token: str, user_token: str, company_id):
        self.company_id = str(company_id)
        self._headers = {
            "Accept": "application/vnd.yclients.v2+json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {partner_token}, User {user_token}",
        }
        self._configured = bool(partner_token and user_token and company_id)

    async def _request(
        self, method: str, path: str, params=None, json=None
    ) -> dict:
        if not self._configured:
            raise YClientsNotConfigured("YClients не настроен")
        url = f"https://api.yclients.com/api/v1{path}"
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, url, headers=self._headers, params=params, json=json
            ) as resp:
                data = await resp.json()
                if not data.get("success"):
                    msg = data.get("meta", {}).get("message") or str(data)
                    logging.warning(f"YClients {method} {path} → {msg}")
                return data

    async def check_connection(self) -> bool:
        """Проверка подключения к API. Возвращает True при success=True."""
        try:
            data = await self._request(
                "GET", f"/book_services/{self.company_id}"
            )
            return data.get("success", False)
        except YClientsNotConfigured:
            return False
        except Exception as e:
            logging.warning(f"YClients check_connection: {e}")
            return False

    async def get_services(self, staff_id=None) -> list[dict]:
        """Список услуг. staff_id — опциональный фильтр."""
        params = {}
        if staff_id is not None:
            params["staff_id"] = staff_id
        data = await self._request(
            "GET", f"/book_services/{self.company_id}", params=params or None
        )
        result = data.get("data")
        return result if isinstance(result, list) else []

    async def get_staff(self, service_id=None) -> list[dict]:
        """Список сотрудников (только bookable=True).
        Возвращает [{id, name, avatar, specialization}]."""
        params = {}
        if service_id is not None:
            params["service_ids[]"] = service_id
        data = await self._request(
            "GET", f"/book_staff/{self.company_id}", params=params or None
        )
        raw = data.get("data")
        items = raw if isinstance(raw, list) else []
        filtered = [
            {
                "id": item.get("id"),
                "name": item.get("name", ""),
                "avatar": item.get("avatar"),
                "specialization": item.get("specialization"),
            }
            for item in items
            if item.get("bookable", True)
        ]
        return filtered

    async def get_available_dates(
        self, staff_id: int, service_id: int
    ) -> list[str]:
        """Список доступных дат в формате YYYY-MM-DD."""
        params = {"staff_id": staff_id, "service_ids[]": service_id}
        data = await self._request(
            "GET", f"/book_dates/{self.company_id}", params=params
        )
        inner = data.get("data") or {}
        dates = inner.get("booking_dates") or []
        return dates if isinstance(dates, list) else []

    async def get_available_times(
        self, staff_id: int, date: str, service_id: int
    ) -> list[dict]:
        """Список доступных слотов: [{time, seance_length, datetime}]."""
        params = {"service_ids[]": service_id}
        path = f"/book_times/{self.company_id}/{staff_id}/{date}"
        data = await self._request("GET", path, params=params)
        result = data.get("data")
        return result if isinstance(result, list) else []

    async def create_booking(
        self,
        fullname: str,
        phone: str,
        email: str,
        service_id,
        staff_id,
        datetime_str: str,
        comment: str = "",
    ) -> tuple[bool, str, int | None]:
        """
        Создание записи. datetime_str: "YYYY-MM-DD HH:MM:SS".
        Возвращает (success, message, record_id или None).
        """
        payload = {
            "phone": phone,
            "fullname": fullname,
            "email": email or "noreply@pilates.local",
            "appointments": [
                {
                    "id": 1,
                    "services": [int(service_id)],
                    "staff_id": int(staff_id),
                    "datetime": datetime_str,
                    "comment": comment,
                }
            ],
        }
        data = await self._request(
            "POST", f"/book_record/{self.company_id}", json=payload
        )
        if data.get("success"):
            record_id = None
            inner = data.get("data")
            if isinstance(inner, dict) and "id" in inner:
                record_id = int(inner["id"])
            elif isinstance(inner, (int, float)):
                record_id = int(inner)
            return True, "Запись создана", record_id
        msg = (
            data.get("meta", {}).get("message")
            or data.get("errors", {}).get("message")
            or str(data)
        )
        if isinstance(msg, dict):
            msg = str(msg)
        return False, msg, None

    async def get_client_records(self, phone: str) -> list[dict]:
        """Записи клиента по телефону за период today..+30 дней."""
        today = date.today().strftime("%Y-%m-%d")
        end = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        params = {"phone": phone, "start_date": today, "end_date": end}
        data = await self._request(
            "GET", f"/records/{self.company_id}", params=params
        )
        result = data.get("data")
        items = result if isinstance(result, list) else []
        return [r for r in items if r.get("active", True)]

    async def cancel_record(self, record_id: int) -> tuple[bool, str]:
        """Отмена записи по id."""
        data = await self._request(
            "DELETE", f"/records/{self.company_id}/{record_id}"
        )
        if data.get("success"):
            return True, "Запись отменена"
        msg = (
            data.get("meta", {}).get("message")
            or data.get("errors", {}).get("message")
            or str(data)
        )
        if isinstance(msg, dict):
            msg = str(msg)
        return False, msg

    async def reschedule_record(
        self,
        record_id: int,
        staff_id: int,
        service_id: int,
        new_datetime: str,
    ) -> tuple[bool, str]:
        """Перенос записи. new_datetime: YYYY-MM-DD HH:MM:SS."""
        payload = {
            "appointments": [
                {
                    "id": record_id,
                    "staff_id": int(staff_id),
                    "services": [int(service_id)],
                    "datetime": new_datetime,
                }
            ]
        }
        data = await self._request(
            "PUT", f"/records/{self.company_id}/{record_id}", json=payload
        )
        if data.get("success"):
            return True, "Перенос выполнен"
        msg = (
            data.get("meta", {}).get("message")
            or data.get("errors", {}).get("message")
            or str(data)
        )
        if isinstance(msg, dict):
            msg = str(msg)
        return False, msg

    async def get_client_by_phone(self, phone: str) -> dict | None:
        """Клиент по телефону или None."""
        params = {"phone": phone, "fields": "id,name,phone,visits"}
        data = await self._request(
            "GET", f"/clients/{self.company_id}", params=params
        )
        result = data.get("data")
        if isinstance(result, list) and result:
            return result[0]
        return None
