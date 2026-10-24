from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.datetime_utils import now_china
from app.db.database import Base


class ReminderPref(Base):
    __tablename__ = "reminder_prefs"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    remind_hour: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class TouchState(Base):
    """触达决策状态（rescue/absence）：内容指纹+发送钟+未读回执证据。

    kind: rescue | absence。last_notif_id 供 read-status 升级换道（travelMate 范本）；
    last_sent_at 驱动 REVIVE 7 天门开着变体；缺席钟（SUNSET 30 天）锚 episode 起点由 gate 计算。
    """

    __tablename__ = "touch_states"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    challenge_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_notif_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_action: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_china, onupdate=now_china)
