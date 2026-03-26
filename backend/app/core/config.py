from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


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


settings = Settings() 

