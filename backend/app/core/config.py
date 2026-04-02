from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    MONGO_URL: str | None = None

    SECRET_KEY: SecretStr

    BUCKET_USER: str
    BUCKET_PASSWORD: SecretStr
    BUCKET_NAME: str
    BUCKET_REGION: str = "us-east-1"

    BUCKET_ENDPOINT_URL: str

    BUCKET_PUBLIC_URL: str

    DEBUG: bool = False
    COOKIE_SECURE: bool = False
    PRESIGNED_URL_EXPIRES_SECONDS: int = 3600

    CORS_ORIGINS: list[str] = Field(default_factory=list)

    ACCESS_TTL_MINUTES: int = 30
    REFRESH_TTL_DAYS: int = 30
    REDIS_URL: str

    @property
    def refresh_ttl_seconds(self) -> int:
        return self.REFRESH_TTL_DAYS * 24 * 60 * 60


settings = Settings()
