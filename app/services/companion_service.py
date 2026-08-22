from __future__ import annotations

from datetime import datetime, timedelta

from app.db.database import async_session
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.services.goal_rule_service import is_ladder, ladder_progress_pct
from app.services.streak_service import calc_streak, day_number_of, today_str

_DROP_LOOKBACK = 4


def _detect_phase(completed: int) -> str:
    if completed <= 7:
        return "adaptation"
    if completed <= 21:
        return "consolidation"
    return "stable"


def _recent_gap(checkins: list, today: str) -> bool:
    if not checkins:
        return False
    valid = {c.date for c in checkins}
    base = datetime.strptime(today, "%Y-%m-%d").date()
    for i in range(1, _DROP_LOOKBACK + 1):
        d = (base - timedelta(days=i)).strftime("%Y-%m-%d")
        if d not in valid:
            return True
    return False


def assess_risk(checkins: list, streak: int, today: str) -> dict[str, object]:
    completed = len(checkins)
    if completed <= 0:
        return {"score": 0, "level": "low", "reasons": [], "micro_action": "", "phase": "adaptation"}

    score = 0
    reasons: list[str] = []
    recent = checkins[-3:]
    bad_mood = any(getattr(c, "mood", "") == "bad" for c in recent)
    under_done = any(
        getattr(c, "completion_pct", 100) is not None and getattr(c, "completion_pct", 100) < 100
        for c in recent
    )
    phase = _detect_phase(completed)

    if streak == 0:
        score += 40
        reasons.append("连续中断后，今天重启就能保住节奏")
    elif streak <= 3:
        score += 20
        reasons.append(f"连击才{streak}天还很脆弱，最易前功尽弃")

    if phase == "adaptation":
        score += 15
        reasons.append("刚起步的适应期是放弃高峰")

    if bad_mood:
        score += 20
        reasons.append("最近心情有些低落，是容易松懈的信号")

    if under_done:
        score += 10
        reasons.append("最近几次没有完全达标，信心略有波动")

    if _recent_gap(checkins, today):
        score += 20
        reasons.append("最近有中断记录，连续中断最难重启")

    score = min(100, score)
    if score >= 60:
        level = "high"
    elif score >= 35:
        level = "medium"
    else:
        level = "low"

    if bad_mood:
        action = "今天先放低要求，只要打个卡记录一下，就算赢"
    elif streak == 0:
        action = "中断不可怕，今天重启一次，节奏就回来了"
    elif phase == "adaptation":
        action = "抽出5分钟做最小版本，先完成再完美"
    elif level == "high" or level == "medium":
        action = "给自己一个5分钟的最小行动，先保住连击"
    else:
        action = "保持你的节奏，今天也稳稳打卡，别让它断在今天"

    return {"score": score, "level": level, "reasons": reasons, "micro_action": action, "phase": phase}


def companion_text(risk: dict[str, object]) -> str:
    reasons = [str(r) for r in risk.get("reasons", [])]
    action = str(risk.get("micro_action") or "")
    if not reasons and not action:
        return "你的节奏保持得很好！今天也稳稳打卡。"
    lead = "我看到" + "、".join(reasons[:2]) + "。"
    return lead + action + "。"


async def load_challenge_state(user_id: str, challenge_id: int) -> dict:
    async with async_session() as session:
        challenge = await ChallengeRepository().get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return {"error": "not_found"}
        checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
        valid = {c.date for c in checkins}
        today = today_str()
        streak = calc_streak(valid, today)
        phase = _detect_phase(len(checkins))
        risk = assess_risk(checkins, streak, today)
        day_number = day_number_of(challenge.start_date, today) if challenge.start_date else 1
        ladder_pct = ladder_progress_pct(challenge, day_number) if is_ladder(challenge) else None
        return {
            "challenge": challenge,
            "checkins": checkins,
            "completed_days": len(checkins),
            "streak": streak,
            "phase": phase,
            "risk": risk,
            "day_number": day_number,
            "ladder_progress_pct": ladder_pct,
        }


def companion_meta(state: dict) -> dict:
    risk = state.get("risk") or {}
    return {
        "challenge_id": state.get("challenge_id"),
        "completed_days": state.get("completed_days", 0),
        "streak": state.get("streak", 0),
        "phase": state.get("phase", ""),
        "risk_level": risk.get("level", "low"),
        "risk_score": risk.get("score", 0),
        "ladder_progress_pct": state.get("ladder_progress_pct"),
    }