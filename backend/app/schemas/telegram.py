import re
from pydantic import BaseModel, field_validator


class TelegramLinkRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("Code must be exactly 6 digits")
        return v


class TelegramLinkStatusResponse(BaseModel):
    is_linked: bool
    telegram_id: str | None


class TelegramLinkCodeRequest(BaseModel):
    telegram_user_id: str


class TelegramLinkCodeResponse(BaseModel):
    code: str


class TelegramUserResponse(BaseModel):
    id: int
    username: str
    telegram_id: str | None

    model_config = {"from_attributes": True}
