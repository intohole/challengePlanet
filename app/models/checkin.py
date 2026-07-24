from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CheckIn(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(Integer, ForeignKey("challenges.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="completed")
    checkin_type: Mapped[str] = mapped_column(String(8), default="full")
    mood: Mapped[str] = mapped_column(String(16), default="good")
    reflection: Mapped[str] = mapped_column(Text, default="")
    ai_feedback: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(16), default="binary")
    task_data: Mapped[str] = mapped_column(Text, default="{}")
    completion_pct: Mapped[float] = mapped_column(Float, default=100.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(Integer, ForeignKey("challenges.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    insight_type: Mapped[str] = mapped_column(String(16), default="daily")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
