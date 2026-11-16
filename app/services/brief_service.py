from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.checkin_repository import CheckInRepository
from app.services.challenge_service import ChallengeService
from app.services.goal_rule_service import daily_target
from app.services.mercy_service import load_valid_dates
from app.services.return_service import brief_return_state
from app.services.streak_service import calc_streak, day_number_of, today_str


async def build_brief_snapshot(session: AsyncSession, user_id: str) -> dict[str, object]:
    """灵犀晨报/今日面的只读挑战摘要（r28）。

    纯只读纪律（#1051）：不建建议、不推进状态、不迁移 resting——哨兵测试
    （tests/test_brief_snapshot_r28.py）钉死 AdaptiveRepository 写链；
    创建语义属主仍是 app 内 today/list 动线。带新鲜重启卡的挑战排首：
    唯一活通道的第一眼必须先是「拉你回来」的那件事。
    """
    service = ChallengeService()
    checkin_repo = CheckInRepository()
    challenges = [
        c for c in await service.get_user_challenges(session, user_id)
        if str(c.status) == "active" and not bool(getattr(c, "is_shared", False))
    ]
    today = today_str()
    items = [await _item_of(session, checkin_repo, c, today) for c in challenges]
    items.sort(key=lambda it: 0 if it["return_ctx"]["restart"] else 1)
    return {"status": "ok", "has_active": bool(items), "challenges": items}


async def _item_of(
    session: AsyncSession, checkin_repo: CheckInRepository, challenge: object, today: str,
) -> dict[str, object]:
    cid = int(challenge.id)
    today_checkin = await checkin_repo.get_by_date(session, cid, today)
    valid_dates = await load_valid_dates(session, cid)
    day_number = day_number_of(str(challenge.start_date), today)
    state = await brief_return_state(session, challenge, today) or {}
    return {
        "id": cid,
        "title": str(challenge.title or ""),
        "icon": str(getattr(challenge, "icon", "") or "🎯"),
        "unit": str(challenge.unit or ""),
        "goal_rule": str(challenge.goal_rule or "fixed"),
        "direction": str(challenge.direction or ""),
        "today_checked": today_checkin is not None,
        "streak": calc_streak(valid_dates, today),
        "day_number": day_number,
        "today_cap": daily_target(challenge, day_number),
        "return_ctx": {
            "gap_days": state.get("gap_days"),
            "return_day": state.get("return_day"),
            "restart": state.get("restart"),
        },
    }
