from __future__ import annotations

import json

from nexus import loads_or
from nexus.logging import get_logger
from nexus.notify import get_notify_client
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.services.goal_rule_service import daily_target, is_cap_mode, is_ladder
from app.services.journey_service import cumulative_avoided, journey_baseline
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.services.streak_service import day_number_of, shift_date, today_str

logger = get_logger("challengePlanet.slip")

SLIP_CARE_INSIGHT = "slip_care"
ATTEMPTS_NOTE = "戒烟研究里平均要尝试约 30 次才能戒断（CDC/BMJ Open），波动是过程的一部分"


def _row_total(rows_by_date: dict[str, dict], date: str) -> float | None:
    row = rows_by_date.get(date)
    if row is None or not int(row.get("checkin_count", 0) or 0):
        return None
    return float(row.get("value", 0) or 0)


def assess_slip(
    challenge: object, daily_rows: list[dict], today: str,
) -> dict[str, object] | None:
    if not (is_cap_mode(challenge) and is_ladder(challenge)):
        return None
    start = str(getattr(challenge, "start_date", "") or "")
    if not start or today <= start:
        return None
    yesterday = shift_date(today, -1)
    rows_by_date = {str(r.get("date")): r for r in daily_rows}
    y_total = _row_total(rows_by_date, yesterday)
    if y_total is None:
        return None
    y_cap = float(daily_target(challenge, day_number_of(start, yesterday)))
    if y_total <= y_cap:
        return None
    day_before = shift_date(today, -2)
    d2_total = _row_total(rows_by_date, day_before)
    if d2_total is not None:
        d2_cap = float(daily_target(challenge, day_number_of(start, day_before)))
        episode_first = d2_total <= d2_cap
    else:
        episode_first = True
    avoided, _ = cumulative_avoided(daily_rows, journey_baseline(challenge))
    return {
        "yesterday_over": True,
        "yesterday_date": yesterday,
        "yesterday_total": y_total,
        "yesterday_cap": y_cap,
        "over_amount": round(y_total - y_cap, 1),
        "episode_first": episode_first,
        "avoided_total": avoided,
    }


def slip_care_text(title: str, unit: str, slip: dict[str, object]) -> tuple[str, str]:
    unit = unit or ""
    over = float(slip["over_amount"] or 0)
    avoided = int(slip["avoided_total"] or 0)
    cap = float(slip["yesterday_cap"] or 0)
    subject = f"「{title}」昨天超了 {over:g} {unit}"
    body = (
        f"已少抽的 {avoided} {unit}都算数，{ATTEMPTS_NOTE}。"
        f"今天上限还是 {cap:g} {unit}；若坡太陡，打开就能把阶梯后移几天——走过的每一天不变。"
    )
    return subject, body


async def _already_sent(session: AsyncSession, challenge_id: int, date: str) -> bool:
    insight = await InsightRepository().get_by_type(session, challenge_id, SLIP_CARE_INSIGHT)
    if insight is None:
        return False
    payload = loads_or(str(insight.content or ""), {})
    return isinstance(payload, dict) and str(payload.get("date", "")) == date


async def _mark_sent(session: AsyncSession, challenge_id: int, user_id: str, date: str) -> None:
    await InsightRepository().create(session, {
        "challenge_id": challenge_id,
        "user_id": user_id,
        "insight_type": SLIP_CARE_INSIGHT,
        "content": json.dumps({"date": date}, ensure_ascii=False),
    })
    await session.flush()


async def send_slip_care() -> None:
    try:
        today = today_str()
        yesterday = shift_date(today, -1)
        async with async_session() as session:
            challenges = await ChallengeRepository().get_all_active(session)
            items: list[dict[str, object]] = []
            for challenge in challenges:
                if not (is_cap_mode(challenge) and is_ladder(challenge)):
                    continue
                start = str(challenge.start_date or "")
                end = str(challenge.end_date or "")
                if not start or today < start or today > end:
                    continue
                if await _already_sent(session, int(challenge.id), yesterday):
                    continue
                rows = await CheckInRepository().get_daily_totals(
                    session, int(challenge.id), start, yesterday,
                )
                slip = assess_slip(challenge, rows, today)
                if slip is None or not bool(slip["episode_first"]):
                    continue
                if await CheckInRepository().count_by_date(session, int(challenge.id), today) > 0:
                    continue
                title, body = slip_care_text(
                    str(challenge.title or "挑战"), str(challenge.unit or ""), slip,
                )
                items.append({
                    "user_id": str(challenge.user_id),
                    "title": title,
                    "content": body,
                    "type": "task",
                    "priority": 3,
                    "app_id": "challengePlanet",
                    "channels": ["in_app", "email"],
                    "link": f"/challengePlanet/?ch={challenge.id}&slip=1",
                    "data": {"challenge_id": challenge.id, "slip_care": True},
                })
                await _mark_sent(session, int(challenge.id), str(challenge.user_id), yesterday)
            if not items:
                logger.info("no slip care to send")
                return
            await get_notify_client().send_many(items)
            await session.commit()
            logger.info("slip care sent to %d challenges", len(items))
    except Exception as e:
        logger.error("slip care task failed: %s", e)
