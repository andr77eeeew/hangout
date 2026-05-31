import httpx
from bot.config import settings


class APIClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url: str = base_url or settings.BACKEND_INTERNAL_URL
        self.api_key: str = api_key or settings.INTERNAL_API_KEY.get_secret_value()
        self.headers: dict[str, str] = {
            "X-Internal-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def generate_link_code(self, telegram_user_id: int) -> str:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            response = await client.post(
                "/internal/telegram/link-code",
                json={"telegram_user_id": str(telegram_user_id)},
            )
            response.raise_for_status()
            data: dict[str, str] = response.json()
            return data["code"]

    async def get_user_by_telegram_id(
        self, telegram_user_id: int
    ) -> dict[str, int | str | None] | None:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            response = await client.get(f"/internal/telegram/users/{telegram_user_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data: dict[str, int | str | None] = response.json()
            return data

    async def get_notification_preferences(
        self, telegram_user_id: int
    ) -> dict[str, int | bool]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            response = await client.get(
                f"/internal/telegram/users/{telegram_user_id}/notification-preferences"
            )
            response.raise_for_status()
            data: dict[str, int | bool] = response.json()
            return data

    async def update_notification_preferences(
        self, telegram_user_id: int, patch: dict[str, bool | None]
    ) -> dict[str, int | bool]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            response = await client.patch(
                f"/internal/telegram/users/{telegram_user_id}/notification-preferences",
                json=patch,
            )
            response.raise_for_status()
            data: dict[str, int | bool] = response.json()
            return data

    async def unlink(self, telegram_user_id: int) -> bool:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self.headers
        ) as client:
            response = await client.delete(
                f"/internal/telegram/users/{telegram_user_id}/link"
            )
            response.raise_for_status()
            return True
