from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SubGoal(Base):
    __tablename__ = "sub_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("challenges.id"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)

    title: Mapped[str] = mapped_column(String(128), nullable=False)
    time_window_start: Mapped[str] = mapped_column(String(5), default="")
    time_window_end: Mapped[str] = mapped_column(String(5), default="")

    target_value: Mapped[float] = mapped_column(Float, default=0.0)
    goal_type: Mapped[str] = mapped_column(String(8), default="soft")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    order: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
