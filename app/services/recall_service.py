"""召回漏斗：触达→打开→看见→行动 四段可观测。

r19 失踪救援上线后「发送成功≠被看见」：唯一真人 8 条通知 0 已读，但 10-13
absence care 送达次日他打开 app 完成了回归+换挡——触达的真正生效时刻是
「打开 app 的瞬间」，没有漏斗就无法回答「这条触达有没有把人拉回来」。
sent 段=ai_insights 的 care 落痕（slip/absence/rescue，先发送后落痕）；
arrived/seen 段=前端深链到达与召回卡曝光上报（recall_events）；
acted 段=通知后 48h 内该挑战的新打卡（邻近归因，不打扰打卡主链）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.logging import get_logger

from app.core.datetime_utils import now_china
from app.models.checkin import AIInsight, CheckIn
from app.models.recall import RecallEvent
from app.services.absence_service import ABSENCE_CARE_INSIGHT
from app.services.rescue_service import RESCUE_CARE_INSIGHT
from app.services.slip_service import SLIP_CARE_INSIGHT
from app.services.streak_service import shift_date, today_str

logger = get_logger("challengePlanet.recall")

CARE_INSIGHTS = (SLIP_CARE_INSIGHT, ABSENCE_CARE_INSIGHT, RESCUE_CARE_INSIGHT)
STAGES = ("arrived", "seen", "acted")
ACTION_WINDOW_HOURS = 48

VALID_CHANNELS = ("rescue", "absence", "slip", "deep")


def _sent_date_of(insight_type: str, content: str) -> str:
    """care 行的发送日（slip 记 slip 日=发送日-1，其余 date 即发送日）。"""
    try:
        payload = json.loads(content or "{}")
    except ValueError:
        payload = {}
    date_str = str(payload.get("date", "") or "")
    if not date_str:
        return ""
    return shift_date(date_str, 1) if insight_type == SLIP_CARE_INSIGHT else date_str


async def track_event(
    session: AsyncSession, user_id: str, challenge_id: int,
    channel: str, stage: str, notif_id: str = "", detail: str = "",
) -> dict[str, object]:
    if stage not in STAGES:
        return {"ok": False, "reason": "invalid stage"}
    if channel not in VALID_CHANNELS:
        return {"ok": False, "reason": "invalid channel"}
    session.add(RecallEvent(
        user_id=str(user_id),
        challenge_id=int(challenge_id or 0),
        channel=str(channel),
        stage=str(stage),
        notif_id=str(notif_id or "")[:64],
        detail=str(detail or "")[:500],
    ))
    await session.commit()
    return {"ok": True}


async def build_funnel(
    session: AsyncSession, days: int = 7, user_id: str | None = None,
) -> dict[str, object]:
    today = today_str()
    cutoff_date = shift_date(today, -max(1, min(days, 60)))
    care_rows = (await session.execute(
        select(AIInsight)
        .where(AIInsight.insight_type.in_(CARE_INSIGHTS))
        .order_by(AIInsight.id.desc())
        .limit(400)
    )).scalars().all()
    events = (await session.execute(
        select(RecallEvent)
        .where(RecallEvent.created_at >= datetime.strptime(cutoff_date, "%Y-%m-%d"))
        .order_by(RecallEvent.id.desc())
        .limit(600)
    )).scalars().all()

    checkin_cursor = datetime.strptime(cutoff_date, "%Y-%m-%d") - timedelta(
        hours=ACTION_WINDOW_HOURS,
    )
    checkins = (await session.execute(
        select(CheckIn).where(CheckIn.timestamp >= checkin_cursor)
        .order_by(CheckIn.id.desc()).limit(800)
    )).scalars().all()

    fun_rows: list[dict[str, object]] = []
    for row in care_rows:
        if user_id is not None and str(row.user_id) != str(user_id):
            continue
        sent = _sent_date_of(row.insight_type, str(row.content or ""))
        if not sent or sent < cutoff_date:
            continue
        ch_id = int(row.challenge_id or 0)
        sent_at = _parse_cn(row.created_at)
        window_end = sent_at + timedelta(hours=ACTION_WINDOW_HOURS) if sent_at else None

        arrived = _first_event(events, ch_id, str(row.insight_type).replace("_care", ""), "arrived", sent_at, window_end)
        seen = _first_event(events, ch_id, str(row.insight_type).replace("_care", ""), "seen", sent_at, window_end)
        acted_at = None
        if window_end:
            acted_at = min(
                (c.timestamp for c in checkins
                 if int(c.challenge_id or 0) == ch_id
                 and str(c.user_id) == str(row.user_id)
                 and sent_at <= _parse_cn(c.timestamp) <= window_end),
                default=None,
            )
        fun_rows.append({
            "insight_id": row.id,
            "channel": row.insight_type.replace("_care", ""),
            "challenge_id": ch_id,
            "user_id": str(row.user_id),
            "sent_date": sent,
            "arrived": arrived.isoformat() if arrived else None,
            "seen": seen.isoformat() if seen else None,
            "acted": acted_at.isoformat() if acted_at else None,
            "content": str(row.content or "")[:120],
        })

    total = len(fun_rows)
    summary = {
        "sent": total,
        "arrived": sum(1 for r in fun_rows if r["arrived"]),
        "seen": sum(1 for r in fun_rows if r["seen"]),
        "acted": sum(1 for r in fun_rows if r["acted"]),
    }
    return {
        "days": days,
        "as_of": today,
        "summary": summary,
        "rows": fun_rows[:50],
        "event_totals": _count_events(events, user_id),
    }


def _count_events(events: list, user_id: str | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in events:
        if user_id is not None and str(e.user_id) != str(user_id):
            continue
        key = f"{e.channel}:{e.stage}"
        out[key] = out.get(key, 0) + 1
    return out


def _first_event(
    events: list, challenge_id: int, channel: str, stage: str,
    sent_at: datetime | None, window_end: datetime | None,
) -> datetime | None:
    if sent_at is None or window_end is None:
        return None
    accepted = {channel, "deep"}
    for e in events:
        if (
            int(e.challenge_id or 0) == challenge_id
            and str(e.channel) in accepted
            and str(e.stage) == stage
            and sent_at <= _parse_cn(e.created_at) <= window_end
        ):
            return _parse_cn(e.created_at)
    return None


def _parse_cn(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    text = str(value or "").replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return now_china()
