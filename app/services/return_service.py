from __future__ import annotations

from nexus.logging import get_logger

from app.repositories.points_repository import ChallengeMetaRepository
from app.services.goal_rule_service import daily_target
from app.services.streak_service import shift_date, today_str

logger = get_logger("challengePlanet.return")

RETURN_WINDOW_DAYS = 3
GAP_MIN_DAYS = 2
BACKFILL_TARGET_DAYS = 3
BONUS_MENDS_PER_BACKFILL = 1


def _gap_run_ending_at(valid_dates: set[str], start: str, first_missing: str) -> tuple[int, str] | None:
    """从 first_missing 起向前数连续缺失日：(缺失天数, 缺口前最后一个有效日)。"""
    gap_days = 0
    walk = first_missing
    while walk >= start and walk not in valid_dates:
        gap_days += 1
        walk = shift_date(walk, -1)
    if gap_days == 0 or walk < start:
        return None
    return gap_days, walk


def return_state_of(challenge: object, valid_dates: set[str], today: str) -> dict[str, object] | None:
    """最近一次缺席（连续 ≥2 天无有效记录）后的回归状态；未在回归窗返回 None。

    在场即回归：今天已打卡→连击段（今天起往前数连续有效日）即回归段；今天未打卡
    但缺口延续到昨天→他正在 app 里，视为回归第 1 天。return_day=回来第 N 天，
    超过 RETURN_WINDOW_DAYS 天退出窗口。micro_target=今日目标的 1/5（向上取整）。
    """
    start = str(getattr(challenge, "start_date", "") or "")
    if not start or today < start:
        return None
    first_missing = shift_date(today, -1)
    if today in valid_dates:
        run = 1
        walk = shift_date(today, -1)
        while walk >= start and walk in valid_dates:
            run += 1
            walk = shift_date(walk, -1)
        first_missing = shift_date(today, -run)
    gap = _gap_run_ending_at(valid_dates, start, first_missing)
    if gap is None or gap[0] < GAP_MIN_DAYS:
        return None
    return_day = run if today in valid_dates else 1
    if return_day > RETURN_WINDOW_DAYS:
        return None
    target = float(daily_target(challenge, 1) or 0)
    micro_target = max(1, round(target / 5)) if target > 0 else 0
    return {
        "gap_days": gap[0],
        "return_day": return_day,
        "walked_days": len(valid_dates),
        "micro_target": micro_target,
        "backfill_target": BACKFILL_TARGET_DAYS,
        "backfill_done": return_day,
    }


async def bonus_mends_of(session, challenge_id: int) -> int:
    from nexus import loads_or

    meta = await ChallengeMetaRepository().get(session, challenge_id)
    if meta is None:
        return 0
    extra = loads_or(str(meta.extra or "{}"), {})
    if not isinstance(extra, dict):
        return 0
    return int(extra.get("bonus_mends", 0) or 0)


async def grant_backfill_reward(
    session, challenge_id: int, episode_anchor: str,
) -> bool:
    """连续回归第 BACKFILL_TARGET_DAYS 天回赠一张免费补签卡（Duolingo 回填模式：
    奖励的是恢复行为本身）。同 episode 只发一次（meta.extra.backfill_episode 锚）。"""
    from nexus import loads_or

    repo = ChallengeMetaRepository()
    meta = await repo.get(session, challenge_id)
    extra: dict[str, object] = {}
    if meta is not None:
        loaded = loads_or(str(meta.extra or "{}"), {})
        if isinstance(loaded, dict):
            extra = dict(loaded)
    if str(extra.get("backfill_episode", "")) == str(episode_anchor):
        return False
    extra["backfill_episode"] = str(episode_anchor)
    extra["bonus_mends"] = int(extra.get("bonus_mends", 0) or 0) + BONUS_MENDS_PER_BACKFILL
    extra["backfill_granted_at"] = today_str()
    await repo.upsert(session, challenge_id, {"extra": _dumps(extra)})
    logger.info("backfill reward granted: challenge %s episode %s", challenge_id, episode_anchor)
    return True


def _dumps(data: dict[str, object]) -> str:
    import json

    return json.dumps(data, ensure_ascii=False)


async def active_return_state(session, challenge, today: str) -> dict[str, object] | None:
    """today-task 入口：活跃挑战的回归态（缺席期打开 app 亦视为回归第 1 天）。"""
    if str(getattr(challenge, "status", "")) != "active":
        return None
    from app.services.mercy_service import load_valid_dates

    return return_state_of(challenge, await load_valid_dates(session, int(challenge.id)), today)


async def return_after_checkin(session, challenge, today: str) -> dict[str, object] | None:
    """checkin 入口：首记后的回归态；第 BACKFILL_TARGET_DAYS 天发回赠免费补签卡。"""
    from app.services.mercy_service import load_valid_dates
    from app.services.streak_service import shift_date

    valid_now = await load_valid_dates(session, int(challenge.id))
    rstate = return_state_of(challenge, valid_now, today)
    if rstate is None:
        return None
    if int(rstate["return_day"]) == BACKFILL_TARGET_DAYS:
        episode_anchor = shift_date(today, int(rstate["gap_days"]) + 1)
        rstate["reward_granted"] = await grant_backfill_reward(
            session, int(challenge.id), str(episode_anchor),
        )
    return rstate
