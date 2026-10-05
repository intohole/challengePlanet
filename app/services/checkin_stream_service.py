"""打卡反馈/周洞察的 SSE 编排（从 API 层下沉）。

service 产出 (event, payload) 事件流元组，SSE 帧序列化由 API 层完成。
反馈流以 checkin_id 为粒度加进程内锁，防止同记录并发重复生成。
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_service import AIService
from app.services.ai_text_sanitizer import sanitize_coach_text
from app.services.checkin_background import (
    build_feedback_prompt_inputs,
    feedback_fallback,
    safe_declaration,
)
from app.services.streak_service import week_dates_of

_feedback_locks: dict[int, asyncio.Lock] = {}


async def feedback_events(
    session: AsyncSession,
    challenge,
    checkin,
    force: bool,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """单条打卡的 AI 教练反馈：缓存直出 → 锁内二次复查 → 流式生成 → 持久化。"""
    repo = CheckInRepository()
    if checkin.ai_feedback and not force:
        yield "done", {
            "content": sanitize_coach_text(checkin.ai_feedback),
            "declaration": str(checkin.declaration or ""),
            "cached": True,
        }
        return
    lock = _feedback_locks.setdefault(checkin.id, asyncio.Lock())
    try:
        async with lock:
            fresh = await repo.get_by_id(session, checkin.id)
            if fresh is None:
                yield "done", {"content": "", "declaration": ""}
                return
            if fresh.ai_feedback and not force:
                yield "done", {
                    "content": sanitize_coach_text(fresh.ai_feedback),
                    "declaration": str(fresh.declaration or ""),
                    "cached": True,
                }
                return
            ai = AIService()
            inputs = await build_feedback_prompt_inputs(session, fresh, challenge)
            pieces: list[str] = []
            try:
                async for piece in ai.stream_daily_feedback(**inputs):
                    pieces.append(piece)
                    yield "token", {"token": piece}
            except Exception:
                content = feedback_fallback(
                    fresh.day_number, fresh.mood, bool(inputs.get("is_soft_exceeded")),
                )
                declaration = ""
            else:
                content = sanitize_coach_text(
                    "".join(pieces).strip(),
                    system=AIService._feedback_system(inputs["mood"]),
                    fallback="",
                )
                declaration = await safe_declaration(ai, challenge.title, fresh.day_number)
            if content:
                await repo.update(session, fresh, {
                    "ai_feedback": content, "declaration": declaration,
                })
                await session.commit()
            yield "done", {"content": content, "declaration": declaration}
    finally:
        _feedback_locks.pop(checkin.id, None)


async def insight_events(
    session: AsyncSession,
    challenge,
    force: bool,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """挑战的周洞察报告：本周已生成则缓存直出，否则流式生成并落库。"""
    insight_repo = InsightRepository()
    latest = await insight_repo.get_latest_weekly(session, challenge.id)
    week_dates = set(week_dates_of())
    fresh = bool(
        latest and latest.created_at
        and latest.created_at.date().strftime("%Y-%m-%d") in week_dates
    )
    if fresh and not force:
        yield "done", {"content": latest.content, "cached": True}
        return
    checkins = await CheckInRepository().get_by_challenge(session, challenge.id)
    checkin_data = [
        {
            "day_number": c.day_number,
            "mood": c.mood,
            "reflection": c.reflection,
            "value": c.value,
            "timestamp": c.timestamp.isoformat(),
            "date": c.date,
        }
        for c in checkins
    ]
    pieces: list[str] = []
    ai = AIAnalysisService()
    async for piece in ai.stream_weekly_report(
        challenge.title, checkin_data, challenge.duration_days
    ):
        pieces.append(piece)
        yield "token", {"token": piece}
    content = sanitize_coach_text("".join(pieces).strip(), max_len=512)
    if not content:
        content = "本周还没有足够记录，先打几天卡再来看看洞察吧"
    await insight_repo.create(session, {
        "challenge_id": challenge.id,
        "user_id": challenge.user_id,
        "insight_type": "weekly",
        "content": content,
    })
    await session.commit()
    yield "done", {"content": content}
