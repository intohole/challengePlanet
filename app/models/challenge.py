from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="build")
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    start_date: Mapped[str] = mapped_column(String(10), default="")
    end_date: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    ai_plan: Mapped[str] = mapped_column(Text, default="[]")
    color: Mapped[str] = mapped_column(String(16), default="#6366f1")
    icon: Mapped[str] = mapped_column(String(16), default="🎯")
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    share_token: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
