from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: SecretStr = SecretStr("dummy_bot_token")
    BACKEND_INTERNAL_URL: str = "http://localhost:8000"
    INTERNAL_API_KEY: SecretStr = SecretStr("dummy_internal_key")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
