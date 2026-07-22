from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Squad(Base):
    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SquadMember(Base):
    __tablename__ = "squad_members"
    __table_args__ = (
        UniqueConstraint("squad_id", "user_id", name="uq_squad_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    squad_id: Mapped[int] = mapped_column(Integer, ForeignKey("squads.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="")
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SquadNudge(Base):
    __tablename__ = "squad_nudges"
    __table_args__ = (
        UniqueConstraint("squad_id", "from_user", "to_user", "nudge_date", name="uq_squad_nudge_daily"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    squad_id: Mapped[int] = mapped_column(Integer, ForeignKey("squads.id"), index=True)
    from_user: Mapped[str] = mapped_column(String(128), nullable=False)
    to_user: Mapped[str] = mapped_column(String(128), nullable=False)
    nudge_date: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
