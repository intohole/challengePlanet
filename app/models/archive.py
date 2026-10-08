from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class JourneyArchive(Base):
    __tablename__ = "journey_archives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    challenge_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(String(16), nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False, default="🎯")
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#8b5cf6")
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="次")
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    total_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_checkins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_best: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avoided_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline: Mapped[float] = mapped_column(nullable=False, default=0.0)
    final_cap: Mapped[float] = mapped_column(nullable=False, default=0.0)
    graduation_state: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    milestones: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    archived_at: Mapped[str] = mapped_column(String(20), nullable=False, default="")
