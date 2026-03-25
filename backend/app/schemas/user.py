from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator, ValidationError
import re

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValidationError("Password must be at least one capital letter is required")
        if not re.search(r"\d", v):
            raise ValidationError("Password must be at least one number is required")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3:
            raise ValidationError("Username must be at least 3 characters")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValidationError("Username must be alphanumeric, digits, or underscore")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    avatar: str | None = None
    email: str
    bio: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserInDB(BaseModel):
    username: str
    email: str
    password: str


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    bio: str | None = None

class AvatarUpdate(BaseModel):
    avatar: str

class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str

