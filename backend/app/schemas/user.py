from datetime import datetime

from pydantic import BaseModel, EmailStr

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

    favorite_tags: list[TagResponse] = []

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: ValidUsername | None = None
    email: EmailStr | None = None
    bio: str | None = None


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: ValidPassword
