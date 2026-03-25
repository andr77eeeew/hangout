from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    MONGO_URL: str
    SECRET_KEY: str

    BUCKET_URL: str
    BUCKET_USER: str
    BUCKET_PASSWORD: str
    BUCKET_NAME: str
    BUCKET_REGION: str


settings = Settings()

