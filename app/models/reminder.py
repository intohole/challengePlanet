from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ReminderPref(Base):
    __tablename__ = "reminder_prefs"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    remind_hour: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
