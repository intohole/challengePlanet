from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.logging import get_logger

from app.models.archive import JourneyArchive
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.services.graduation_service import graduation_block
from app.services.journey_service import cumulative_avoided, journey_baseline
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import day_number_of, today_str

logger = get_logger("challengePlanet.archive")


def best_streak(valid_dates: set[str]) -> int:
    if not valid_dates:
        return 0
    best = 0
    run = 0
    prev: date | None = None
    for day_str in sorted(valid_dates):
        try:
            cur = date.fromisoformat(day_str)
        except ValueError:
            continue
        run = run + 1 if (prev is not None and (cur - prev).days == 1) else 1
        best = max(best, run)
        prev = cur
    return best


async def summarize(session: AsyncSession, challenge: object) -> dict[str, object]:
    from app.services.challenge_service import ChallengeService
    from app.services.goal_rule_service import is_ladder

    checkin_repo = CheckInRepository()
    total_checkins = await checkin_repo.count_by_challenge(session, int(challenge.id))
    valid = await load_valid_dates(session, int(challenge.id))
    stats = await ChallengeService().get_challenge_stats(session, challenge, valid_dates=valid)
    start = str(challenge.start_date or "")
    today = today_str()
    rows = await checkin_repo.get_daily_totals(session, int(challenge.id), start, today)
    baseline = journey_baseline(challenge)
    avoided = 0
    reached: set[str] = set()
    if str(getattr(challenge, "direction", "") or "") == "decrease" and baseline > 0:
        avoided, reached = cumulative_avoided(rows, baseline)
    grad_state = ""
    if is_ladder(challenge):
        day_number = day_number_of(start, today)
        block = graduation_block(challenge, day_number, date.fromisoformat(start), date.fromisoformat(today))
        if block:
            grad_state = str(block.get("state", "") or "")
    return {
        "total_checkins": total_checkins,
        "completed_days": int(stats["completed_days"]),
        "streak_best": best_streak(valid),
        "avoided_total": avoided,
        "baseline": baseline,
        "final_cap": float(getattr(challenge, "ladder_goal", 0) or 0),
        "graduation_state": grad_state,
        "milestones": sorted(reached),
    }


async def archive_and_delete(session: AsyncSession, challenge: object) -> dict[str, object]:
    summary = await summarize(session, challenge)
    archive = JourneyArchive(
        user_id=str(challenge.user_id),
        challenge_id=int(challenge.id),
        title=str(challenge.title or ""),
        category=str(challenge.category or "other"),
        task_type=str(challenge.task_type or "binary"),
        icon=str(challenge.icon or "🎯"),
        color=str(challenge.color or "#8b5cf6"),
        unit=str(challenge.unit or "次"),
        start_date=str(challenge.start_date or ""),
        end_date=str(challenge.end_date or ""),
        total_days=int(challenge.duration_days or 0),
        completed_days=int(summary["completed_days"]),
        total_checkins=int(summary["total_checkins"]),
        streak_best=int(summary["streak_best"]),
        avoided_total=int(summary["avoided_total"]),
        baseline=float(summary["baseline"]),
        final_cap=float(summary["final_cap"]),
        graduation_state=str(summary["graduation_state"]),
        milestones=json.dumps(list(summary.get("milestones") or []), ensure_ascii=False),
        archived_at=today_str(),
    )
    session.add(archive)
    await session.flush()
    await ChallengeRepository().delete_with_children(session, int(challenge.id))
    logger.info(
        "journey archived: user=%s challenge=%s days=%s avoided=%s",
        challenge.user_id, challenge.id, summary["completed_days"], summary["avoided_total"],
    )
    return summary


async def user_summary(session: AsyncSession, user_id: str) -> dict[str, object]:
    from app.services.challenge_service import ChallengeService

    challenges = await ChallengeService().get_user_challenges(session, user_id)
    checkin_days = 0
    best = 0
    avoided = 0
    for challenge in challenges:
        summary = await summarize(session, challenge)
        checkin_days += int(summary["completed_days"])
        best = max(best, int(summary["streak_best"]))
        avoided += int(summary["avoided_total"])
    result = await session.execute(
        select(JourneyArchive).where(JourneyArchive.user_id == user_id)
    )
    archives = list(result.scalars().all())
    for r in archives:
        checkin_days += int(r.completed_days or 0)
        best = max(best, int(r.streak_best or 0))
        avoided += int(r.avoided_total or 0)
    return {
        "checkin_days": checkin_days,
        "best_streak": best,
        "avoided_total": avoided,
        "active_count": len(challenges),
        "archive_count": len(archives),
    }


async def list_archives(session: AsyncSession, user_id: str) -> list[dict[str, object]]:
    result = await session.execute(
        select(JourneyArchive).where(JourneyArchive.user_id == user_id).order_by(JourneyArchive.id)
    )
    rows = list(result.scalars().all())
    items: list[dict[str, object]] = []
    for r in rows:
        try:
            marks = json.loads(str(r.milestones or "[]"))
            if not isinstance(marks, list):
                marks = []
        except ValueError:
            marks = []
        items.append({
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "icon": r.icon,
            "color": r.color,
            "unit": r.unit,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "total_days": r.total_days,
            "completed_days": r.completed_days,
            "total_checkins": r.total_checkins,
            "streak_best": r.streak_best,
            "avoided_total": r.avoided_total,
            "baseline": r.baseline,
            "final_cap": r.final_cap,
            "graduation_state": r.graduation_state,
            "milestones": marks,
            "archived_at": r.archived_at,
        })
    return items
