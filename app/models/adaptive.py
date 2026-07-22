from __future__ import annotations

from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AdaptiveSuggestion(Base):
    __tablename__ = "adaptive_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(Integer, ForeignKey("challenges.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="lighten")
    reason: Mapped[str] = mapped_column(Text, default="")
    task_json: Mapped[str] = mapped_column(Text, default="{}")
    target_day: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
