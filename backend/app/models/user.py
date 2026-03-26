from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, func, DateTime
from datetime import datetime
from app.core.database import Base


class UserRole(str, Enum):
    client = "client"
    moderator = "moderator"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_role: Mapped[UserRole] = mapped_column(
        default=UserRole.client, server_default="client"
    )
