from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class NotificationPreferences(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    membership_updates: Mapped[bool] = mapped_column(
        default=True, server_default="true"
    )
    activity_reminders: Mapped[bool] = mapped_column(
        default=True, server_default="true"
    )
    tag_subscriptions: Mapped[bool] = mapped_column(default=True, server_default="true")
    report_updates: Mapped[bool] = mapped_column(default=True, server_default="true")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        if "report_updates" not in kwargs:
            self.report_updates = True
