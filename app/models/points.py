from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.datetime_utils import now_china
from app.db.database import Base


class PointsLedger(Base):
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    ref_id: Mapped[str] = mapped_column(String(64), default="", nullable=True)
    week_key: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_china)


class StreakAction(Base):
    __tablename__ = "streak_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[int] = mapped_column(Integer, ForeignKey("challenges.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    action_date: Mapped[str] = mapped_column(String(10), nullable=False)
    cost: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_china)


class ChallengeMeta(Base):
    __tablename__ = "challenge_meta"

    challenge_id: Mapped[int] = mapped_column(Integer, ForeignKey("challenges.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    squad_id: Mapped[int] = mapped_column(Integer, nullable=True)
    extra: Mapped[str] = mapped_column(Text, default="{}")
