from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.datetime_utils import now_china
from app.db.database import Base


class RecallEvent(Base):
    __tablename__ = "recall_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    challenge_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    notif_id: Mapped[str] = mapped_column(String(64), default="", nullable=True)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_china, index=True)
