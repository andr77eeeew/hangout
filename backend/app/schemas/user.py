from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.validators import ValidPassword, ValidUsername


class UserCreate(BaseModel):
    username: ValidUsername
    email: EmailStr
    password: ValidPassword


class TagResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    username: str
    avatar: str | None = None
    banner: str | None = None
    email: str
    bio: str | None = None
    created_at: datetime
    is_banned: bool = False

    favorite_tags: list[TagResponse] = []

    model_config = {"from_attributes": True}

    @field_validator("is_banned", mode="before")
    @classmethod
    def default_is_banned(cls, value: bool | None) -> bool:
        if value is None:
            return False
        return value


class UserUpdate(BaseModel):
    username: ValidUsername | None = None
    email: EmailStr | None = None
    bio: str | None = None


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: ValidPassword
