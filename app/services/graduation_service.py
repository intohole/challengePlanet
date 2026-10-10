from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from nexus import loads_or
from nexus.logging import get_logger
from nexus.notify import get_notify_client

from app.db.database import async_session
from app.models.challenge import Challenge
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.services.goal_rule_service import is_cap_mode, is_ladder, ladder_goal_day

logger = get_logger("challengePlanet.graduation")

PUSH_INSIGHT_TYPE = "journey_push"
APPROACH_DAYS = 3


def graduation_goal_day(challenge: object) -> int | None:
    if not (is_ladder(challenge) and is_cap_mode(challenge)):
        return None
    return ladder_goal_day(challenge)


def graduation_block(
    challenge: object, day_number: int, start_date: date, today: date,
) -> dict[str, object] | None:
    goal_day = graduation_goal_day(challenge)
    if goal_day is None:
        return None
    grad_date = start_date + timedelta(days=goal_day - 1)
    days_left = (grad_date - today).days
    graduated = day_number >= goal_day
    end_date_str = str(getattr(challenge, "end_date", "") or "")
    keep_total = 0
    if end_date_str:
        try:
            keep_total = max(0, (date.fromisoformat(end_date_str) - grad_date).days + 1)
        except ValueError:
            keep_total = 0
    return {
        "state": "graduated" if graduated else ("approaching" if 0 <= days_left <= APPROACH_DAYS else "on_track"),
        "days_to_graduation": max(0, days_left),
        "graduation_date": grad_date.isoformat(),
        "final_cap": float(getattr(challenge, "ladder_goal", 0) or 0),
        "keep_days_total": keep_total,
        "keep_day": max(0, day_number - goal_day + 1) if graduated else 0,
    }


def milestone_push_rows(
    daily_rows: list[dict[str, object]], baseline: float, thresholds: tuple[int, ...],
) -> list[int]:
    """今天新跨过的里程碑（昨日累计 < t <= 当前累计）；存量历史跨越天然不命中。"""
    avoided_total = 0.0
    for row in daily_rows:
        if not int(row.get("checkin_count", 0) or 0):
            continue
        avoided_total += max(0.0, baseline - float(row.get("value", 0) or 0))
    avoided_yesterday = avoided_total
    for row in reversed(daily_rows):
        if not int(row.get("checkin_count", 0) or 0):
            continue
        avoided_yesterday -= max(0.0, baseline - float(row.get("value", 0) or 0))
        break
    return [t for t in thresholds if avoided_yesterday < t <= avoided_total]


async def _load_push_state(session: AsyncSession, challenge: Challenge) -> tuple[object | None, dict[str, object]]:
    row = await InsightRepository().get_by_type(session, int(challenge.id), PUSH_INSIGHT_TYPE)
    if row is None:
        return None, {}
    payload = loads_or(str(row.content or ""), {})
    return row, (payload if isinstance(payload, dict) else {})


async def _mark_pushed(session: AsyncSession, challenge: Challenge, row: object | None, state: dict[str, object], key: str) -> None:
    state[key] = True
    content = json.dumps(state, ensure_ascii=False)
    if row is not None:
        row.content = content  # type: ignore[attr-defined]
    else:
        await InsightRepository().create(session, {
            "challenge_id": challenge.id,
            "user_id": challenge.user_id,
            "insight_type": PUSH_INSIGHT_TYPE,
            "content": content,
        })
    await session.flush()


def _push_item(challenge: Challenge, title: str, body: str, link: str) -> dict[str, object]:
    return {
        "user_id": str(challenge.user_id),
        "title": title,
        "content": body,
        "type": "task",
        "priority": 3,
        "app_id": "challengePlanet",
        "channels": ["in_app", "email"],
        "link": link,
        "data": {"challenge_id": challenge.id, "journey_push": True},
    }


def milestone_push_text(unit: str, threshold: int) -> tuple[str, str]:
    unit = unit or ""
    return (
        f"🏅 累计少抽 {threshold} 根",
        f"旅程又立起一块里程碑：累计少抽 {threshold} 根{unit}。打开星轨看看你的减量旅程。",
    )


def graduation_push_text(
    challenge: Challenge, avoided: int, pct: int, unit: str,
) -> tuple[str, str]:
    unit = unit or ""
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    goal = float(getattr(challenge, "ladder_goal", 0) or 0)
    title = f"🎓 「{challenge.title}」阶梯毕业"
    body = (
        f"从每天约 {start:g} {unit}走到 {goal:g} {unit}，累计少抽 {avoided} {unit}（-{pct}%）。"
        "毕业证书已生成，来保存这份成果。"
    )
    return title, body


class GraduationPushService:
    """旅程成果推送：每小时扫描，里程碑/毕业各只推一次（insight 去重）。"""

    def __init__(self) -> None:
        self._checkin_repo = CheckInRepository()
        self._journey_repo = CheckInRepository()

    async def scan_challenge(self, session: AsyncSession, challenge: Challenge) -> list[dict[str, object]]:
        from app.services.journey_service import journey_baseline, recent_average, reduction_pct
        from app.services.streak_service import day_number_of, today_str

        goal_day = graduation_goal_day(challenge)
        baseline = journey_baseline(challenge)
        today = today_str()
        rows = await self._checkin_repo.get_daily_totals(
            session, int(challenge.id), str(challenge.start_date), today,
        )
        state_row, state = await _load_push_state(session, challenge)
        items: list[dict[str, object]] = []
        link = f"/challengePlanet/?ch={challenge.id}&grad=1"
        new_ms = [t for t in milestone_push_rows(rows, baseline, (50, 100, 200, 500, 1000)) if not state.get(f"avoided_{t}")]
        for threshold in new_ms:
            title, body = milestone_push_text(str(getattr(challenge, "unit", "") or ""), threshold)
            items.append(_push_item(challenge, title, body, link))
            await _mark_pushed(session, challenge, state_row, state, f"avoided_{threshold}")
        if goal_day is not None and not state.get("graduated"):
            day_number = day_number_of(str(challenge.start_date), today)
            if day_number and day_number >= goal_day:
                avoided = sum(
                    max(0.0, baseline - float(r.get("value", 0) or 0))
                    for r in rows if int(r.get("checkin_count", 0) or 0)
                )
                title, body = graduation_push_text(
                    challenge, int(round(avoided)), reduction_pct(baseline, recent_average(rows)),
                    str(getattr(challenge, "unit", "") or ""),
                )
                items.append(_push_item(challenge, title, body, link))
                await _mark_pushed(session, challenge, state_row, state, "graduated")
        if items:
            await session.commit()
        return items

    async def send_journey_pushes(self) -> None:
        try:
            async with async_session() as session:
                from app.repositories.challenge_repository import ChallengeRepository
                challenges = await ChallengeRepository().get_all_active(session)
                items: list[dict[str, object]] = []
                for challenge in challenges:
                    if str(getattr(challenge, "direction", "") or "") != "decrease":
                        continue
                    try:
                        items.extend(await self.scan_challenge(session, challenge))
                    except Exception as e:
                        logger.warning("journey push skip ch=%s: %s", challenge.id, e)
                if not items:
                    return
                await get_notify_client().send_many(items)
                await session.commit()
                logger.info("journey pushes sent: %d items", len(items))
        except Exception as e:
            logger.error("journey push task failed: %s", e)
