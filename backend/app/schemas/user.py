import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.validators import ValidPassword, ValidUsername


class UserCreate(BaseModel):
    username: ValidUsername
    email: EmailStr
    password: ValidPassword


class UserResponse(BaseModel):
    id: int
    username: str
    avatar: str | None = None
    banner: str | None = None
    email: str
    bio: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserInDB(BaseModel):
    username: str
    email: str
    password: str


class UserUpdate(BaseModel):
    username: ValidUsername | None = None
    email: EmailStr | None = None
    bio: str | None = None


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: ValidPassword
