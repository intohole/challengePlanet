from __future__ import annotations

import json

from nexus import loads_or
from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.checkin_repository import InsightRepository
from app.services.goal_rule_service import daily_target, is_cap_mode, is_ladder
from app.services.journey_service import cumulative_avoided, journey_baseline
from app.services.slip_service import SLIP_CARE_INSIGHT
from app.services.streak_service import day_number_of, shift_date, today_str

logger = get_logger("challengePlanet.absence")

ABSENCE_CARE_INSIGHT = "absence_care"
MIN_ABSENT_DAYS = 2
TOUCH_GAP_DAYS = 2


def assess_absence(
    challenge: object, daily_rows: list[dict], today: str,
) -> dict[str, object] | None:
    """cap 阶梯挑战连续 ≥2 天无记录的失踪判定：失踪是 slip 之外的另一种高危状态。

    前提：建档后至少记过一次（从未记录=尚未启程，不是失踪）；
    今天已有记录=失踪期已结束，不再判缺席。
    """
    if not (is_cap_mode(challenge) and is_ladder(challenge)):
        return None
    start = str(getattr(challenge, "start_date", "") or "")
    if not start or today <= start:
        return None
    rows_by_date = {str(r.get("date")): r for r in daily_rows}
    if int(rows_by_date.get(today, {}).get("checkin_count", 0) or 0) > 0:
        return None
    last_date: str | None = None
    for row in reversed(daily_rows):
        if int(row.get("checkin_count", 0) or 0) and str(row.get("date")) != today:
            last_date = str(row.get("date"))
            break
    if last_date is None:
        return None
    absent_days = 0
    cursor = shift_date(today, -1)
    while cursor >= start and cursor not in rows_by_date:
        absent_days += 1
        cursor = shift_date(cursor, -1)
    if absent_days < MIN_ABSENT_DAYS or cursor < start:
        return None
    last_row = rows_by_date.get(last_date, {})
    last_value = float(last_row.get("value", 0) or 0)
    cap_now = float(daily_target(challenge, day_number_of(start, today)))
    avoided, _ = cumulative_avoided(daily_rows, journey_baseline(challenge))
    return {
        "absent_days": absent_days,
        "last_record_date": last_date,
        "last_value": last_value,
        "cap_now": cap_now,
        "avoided_total": avoided,
        "suggest_adjust": last_value > cap_now,
    }


def absence_care_text(title: str, unit: str, absence: dict[str, object]) -> tuple[str, str]:
    unit = unit or ""
    days = int(absence["absent_days"] or 0)
    cap = float(absence["cap_now"] or 0)
    avoided = int(absence["avoided_total"] or 0)
    subject = f"「{title}」{days} 天没见了"
    kept = f"已少抽的 {avoided} {unit}都还在；" if avoided > 0 else ""
    body = (
        f"今天上限 {cap:g} {unit}，回来记一笔，就算今天守住。"
        f"{kept}坡太陡的话，打开就能把阶梯后移几天——走过的每一天不变。"
    )
    return subject, body


def touch_sent_date(insight_type: str, payload: object) -> str | None:
    """insight 记录的「回应日期」换算成触达发送日：slip 记 slip 日（发送日-1），absence 记发送日。"""
    if not isinstance(payload, dict):
        return None
    date_str = str(payload.get("date", "") or "")
    if not date_str:
        return None
    return shift_date(date_str, 1) if insight_type == SLIP_CARE_INSIGHT else date_str


async def load_touch_dates(session: AsyncSession, challenge_id: int) -> dict[str, str]:
    """两类触达（slip/absence）最近一次的发送日期表 {kind: sent_date}。"""
    repo = InsightRepository()
    touches: dict[str, str] = {}
    for insight_type in (SLIP_CARE_INSIGHT, ABSENCE_CARE_INSIGHT):
        row = await repo.get_by_type(session, challenge_id, insight_type)
        if row is None:
            continue
        sent = touch_sent_date(insight_type, loads_or(str(row.content or ""), {}))
        if sent:
            touches[insight_type] = sent
    return touches


def absence_due(touches: dict[str, str], today: str) -> bool:
    """距任何一次触达（slip/absence）不足 TOUCH_GAP_DAYS 天则静默。"""
    for sent in touches.values():
        if sent and shift_date(sent, TOUCH_GAP_DAYS) > today:
            return False
    return True


async def same_episode_cared(session: AsyncSession, challenge_id: int, last_record_date: str) -> bool:
    """上次 absence 触达后没有新记录 = 同一次失踪期内，不重复打扰。"""
    row = await InsightRepository().get_by_type(session, challenge_id, ABSENCE_CARE_INSIGHT)
    if row is None:
        return False
    payload = loads_or(str(row.content or ""), {})
    if not isinstance(payload, dict):
        return False
    return str(payload.get("last_record_date", "")) == str(last_record_date)


async def _legacy_touch_sent_at(
    session: AsyncSession, challenge_id: int, last_record_date: str,
) -> tuple[object, int] | None:
    """TouchState 上线前的存量回退：同缺席期 insight 触达 → (created_at, notif_id=0)。"""
    row = await InsightRepository().get_by_type(session, challenge_id, ABSENCE_CARE_INSIGHT)
    if row is None:
        return None
    payload = loads_or(str(row.content or ""), {})
    if isinstance(payload, dict) and str(payload.get("last_record_date", "")) == str(last_record_date):
        return row.created_at, 0
    return None


async def collect_absence_items(
    session: AsyncSession, challenges: list,
) -> list[dict[str, object]]:
    """扫描全部活跃挑战，返回待发送的 absence 触达（含标记元数据，未发送未落痕）。

    频率层=2 天冷却（slip/absence 共享）；语义层=touch_gate（首触单发→7 天 REVIVE
    门开着变体→30 天 SUNSET 诚实退场），legacy insight 回退防新表无历史重发首触。
    """
    today = today_str()
    from app.repositories.checkin_repository import CheckInRepository

    checkin_repo = CheckInRepository()
    items: list[dict[str, object]] = []
    for challenge in challenges:
        if not (is_cap_mode(challenge) and is_ladder(challenge)):
            continue
        start = str(challenge.start_date or "")
        end = str(challenge.end_date or "")
        if not start or today < start or today > end:
            continue
        if await checkin_repo.count_by_date(session, int(challenge.id), today) > 0:
            continue
        rows = await checkin_repo.get_daily_totals(session, int(challenge.id), start, today)
        absence = assess_absence(challenge, rows, today)
        if absence is None:
            continue
        last_record = str(absence["last_record_date"])
        touches = await load_touch_dates(session, int(challenge.id))
        if not absence_due(touches, today):
            continue
        legacy = await _legacy_touch_sent_at(session, int(challenge.id), last_record)
        from app.services.touch_gate_service import decide_touch_kind

        gate = await decide_touch_kind(
            session, kind="absence", challenge_id=int(challenge.id),
            user_id=str(challenge.user_id), episode_anchor=last_record, today=today,
            legacy_sent_at=legacy[0] if legacy else None,
        )
        if gate["action"] not in ("send", "revive"):
            logger.info(
                "absence gate %s: challenge %s episode since %s (%s)",
                gate["action"], challenge.id, last_record, gate["reason"],
            )
            continue
        title, body = absence_care_text(
            str(challenge.title or "挑战"), str(challenge.unit or ""), absence,
        )
        link_rc = "absence"
        if gate["action"] == "revive":
            title, body = absence_revive_text(
                str(challenge.title or "挑战"), str(challenge.unit or ""), absence,
                lane=str(gate["lane"]),
            )
            link_rc = "revive"
        items.append({
            "payload": {
                "user_id": str(challenge.user_id),
                "title": title,
                "content": body,
                "type": "task",
                "priority": 3,
                "app_id": "challengePlanet",
                "channels": ["in_app", "email"],
                "link": f"/challengePlanet/?ch={challenge.id}&rc={link_rc}",
                "data": {"challenge_id": challenge.id, "absence_care": True,
                         "touch_action": str(gate["action"])},
            },
            "challenge_id": int(challenge.id),
            "user_id": str(challenge.user_id),
            "absence": absence,
            "gate": gate,
        })
    return items


def absence_revive_text(
    title: str, unit: str, absence: dict[str, object], lane: str,
) -> tuple[str, str]:
    """同缺席期 7 天后的再邀请：未读=门开着；已读未行动=换道（给安静出口）。"""
    unit = unit or ""
    cap = float(absence["cap_now"] or 0)
    avoided = int(absence["avoided_total"] or 0)
    subject = f"「{title}」的门一直开着"
    if lane == "switch":
        body = (
            f"上次说的话你大概看到了，这次不催打卡。今天上限 {cap:g} {unit}，"
            "想继续，回来记一笔就算守住；不想硬扛，打开把阶梯后移几天也一样——"
            "走过的每一天不变。"
        )
        return subject, body
    kept = f"已少抽的 {avoided} {unit}都还在；" if avoided > 0 else ""
    return subject, (
        f"回来不需要理由。今天上限 {cap:g} {unit}，记一笔就算今天守住。{kept}"
        "坡想调随时可以调。"
    )


async def mark_absence_sent(
    session: AsyncSession, challenge_id: int, user_id: str, absence: dict[str, object],
    gate: dict[str, object] | None = None, notif_id: int = 0,
) -> None:
    await InsightRepository().create(session, {
        "challenge_id": challenge_id,
        "user_id": user_id,
        "insight_type": ABSENCE_CARE_INSIGHT,
        "content": json.dumps({
            "date": today_str(),
            "absent_days": int(absence.get("absent_days", 0) or 0),
            "last_record_date": str(absence.get("last_record_date", "")),
        }, ensure_ascii=False),
    })
    if gate is not None:
        from app.services.touch_gate_service import mark_touch_sent

        await mark_touch_sent(
            session, user_id=user_id, challenge_id=challenge_id, kind="absence",
            fingerprint_value=str(gate.get("fingerprint", "")),
            notif_id=notif_id, action=str(gate.get("action", "")),
        )
