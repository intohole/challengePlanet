from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="build")

    task_type: Mapped[str] = mapped_column(String(16), default="binary")
    target_value: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(16), default="次")
    direction: Mapped[str] = mapped_column(String(8), default="increase")
    goal_type: Mapped[str] = mapped_column(String(8), default="hard")

    decompose_mode: Mapped[str] = mapped_column(String(16), default="none")
    slot_hours: Mapped[int] = mapped_column(Integer, default=1)
    slot_target_value: Mapped[float] = mapped_column(Float, default=0.0)

    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    start_date: Mapped[str] = mapped_column(String(10), default="")
    end_date: Mapped[str] = mapped_column(String(10), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")

    ai_plan: Mapped[str] = mapped_column(Text, default="[]")
    color: Mapped[str] = mapped_column(String(16), default="#6366f1")
    icon: Mapped[str] = mapped_column(String(16), default="🎯")
    scene_template: Mapped[str] = mapped_column(String(32), default="")

    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    share_token: Mapped[str] = mapped_column(String(64), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
