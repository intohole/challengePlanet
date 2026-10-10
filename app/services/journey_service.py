from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.checkin_repository import CheckInRepository
from app.services.goal_rule_service import (
    daily_target,
    is_cap_mode,
    is_ladder,
    ladder_cap_of,
    ladder_goal_day,
    parse_ladder_adjustments,
)

MONEY_PER_UNIT = 0.9
MONEY_NOTE = "按约 ¥18/包（20 支）估算"
AVOIDED_MILESTONES = (50, 100, 200, 500, 1000)
GUARD_DAYS = 7

HEALTH_MILESTONES: list[dict[str, object]] = [
    {"key": "hr_20min", "offset": timedelta(minutes=20), "title": "心率开始回落",
     "detail": "最后一支烟 20 分钟后，心率和血压开始向正常回落"},
    {"key": "co_12h", "offset": timedelta(hours=12), "title": "一氧化碳归常",
     "detail": "12 小时后，血液中一氧化碳水平恢复正常"},
    {"key": "circ_2w", "offset": timedelta(days=14), "title": "循环与肺功能改善",
     "detail": "2 周后，血液循环改善，肺功能开始提升"},
    {"key": "breath_1m", "offset": timedelta(days=30), "title": "呼吸更轻松",
     "detail": "1 个月后，气短减少，体能与精力回升"},
    {"key": "circ_3m", "offset": timedelta(days=90), "title": "循环显著增强",
     "detail": "3 个月后，血液循环与肺功能显著改善"},
    {"key": "chd_1y", "offset": timedelta(days=365), "title": "冠心病风险减半",
     "detail": "1 年后，冠心病的额外风险降至吸烟者的一半"},
]
HEALTH_SOURCE_NOTE = "通用公共卫生恢复口径（美国癌症协会/疾控中心），个体感受因人而异"


def journey_baseline(challenge: object) -> float:
    if is_ladder(challenge) and float(getattr(challenge, "ladder_start", 0) or 0) > 0:
        return float(getattr(challenge, "ladder_start", 0))
    return float(getattr(challenge, "target_value", 0) or 0)


def adjustment_rows(challenge: object, start_date: date) -> list[dict[str, object]]:
    try:
        adjustments = parse_ladder_adjustments(getattr(challenge, "ladder_adjust", ""))
    except Exception:
        adjustments = []
    rows: list[dict[str, object]] = []
    for adj in adjustments:
        day = int(adj["day"])
        rows.append({
            "date": (start_date + timedelta(days=day - 1)).isoformat(),
            "shift": int(adj["shift"]),
        })
    return rows


def _ladder_goal_day_number(challenge: object) -> int:
    goal_day = ladder_goal_day(challenge)
    if goal_day is not None:
        return goal_day
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    goal = float(getattr(challenge, "ladder_goal", 0) or 0)
    if start <= goal:
        return 1
    step = float(getattr(challenge, "ladder_step", 1) or 1) or 1.0
    interval = max(1, int(getattr(challenge, "ladder_interval", 1) or 1))
    return int(-(-(start - goal) // step)) * interval + 1


def ladder_stage_info(challenge: object, day_number: int) -> dict[str, int]:
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    goal = float(getattr(challenge, "ladder_goal", 0) or 0)
    step = float(getattr(challenge, "ladder_step", 1) or 1) or 1.0
    interval = max(1, int(getattr(challenge, "ladder_interval", 1) or 1))
    if start == goal:
        return {"stage": 1, "total_stages": 1}
    total_stages = int(round(abs(start - goal) / step)) + 1
    cap_now = ladder_cap_of("decrease", start, goal, interval, step, max(1, day_number))
    stage_now = int(round((start - cap_now) / step)) + 1
    return {"stage": max(1, min(stage_now, total_stages)), "total_stages": max(1, total_stages)}


def cumulative_avoided(
    daily_rows: list[dict[str, object]], baseline: float,
) -> tuple[int, set[str]]:
    total = 0.0
    reached: set[str] = set()
    for row in daily_rows:
        if not int(row.get("checkin_count", 0) or 0):
            continue
        day_total = float(row.get("value", 0) or 0)
        total += max(0.0, baseline - day_total)
        for threshold in AVOIDED_MILESTONES:
            if total >= threshold:
                reached.add(f"avoided_{threshold}")
    return int(round(total)), reached


def recent_average(daily_rows: list[dict[str, object]]) -> float:
    totals = [float(r.get("value", 0) or 0) for r in daily_rows if int(r.get("checkin_count", 0) or 0)]
    if not totals:
        return 0.0
    window = totals[-7:] if len(totals) >= 3 else totals
    return round(sum(window) / len(window), 2)


def reduction_pct(baseline: float, avg: float) -> int:
    if baseline <= 0:
        return 0
    return max(0, min(100, int(round((baseline - avg) / baseline * 100.0))))


def trailing_guard_days(
    daily_rows: list[dict[str, object]], challenge: object, start_date: date,
) -> int:
    streak = 0
    for row in reversed(daily_rows):
        if not int(row.get("checkin_count", 0) or 0):
            break
        try:
            day_number = (
                datetime.strptime(str(row["date"]), "%Y-%m-%d").date() - start_date
            ).days + 1
        except Exception:
            day_number = 1
        cap = daily_target(challenge, max(1, day_number))
        if float(row.get("value", 0) or 0) <= cap:
            streak += 1
        else:
            break
    return streak


def health_block(anchor: date, anchor_label: str, today: date) -> dict[str, object]:
    milestones: list[dict[str, object]] = []
    for item in HEALTH_MILESTONES:
        reach_dt = anchor + item["offset"]  # type: ignore[operator]
        milestones.append({
            "key": str(item["key"]), "title": str(item["title"]),
            "detail": str(item["detail"]),
            "reach_date": reach_dt.isoformat(),
            "reached": today >= reach_dt,
        })
    return {
        "anchor_date": anchor.isoformat(), "anchor_label": anchor_label,
        "milestones": milestones, "source_note": HEALTH_SOURCE_NOTE,
    }


def milestone_rows(
    avoided_reached: set[str], stage_info: dict[str, int], guard_days: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for threshold in AVOIDED_MILESTONES:
        key = f"avoided_{threshold}"
        rows.append({"key": key, "label": f"累计少抽 {threshold} 根", "reached": key in avoided_reached})
    half = stage_info["total_stages"] // 2 + stage_info["total_stages"] % 2
    rows.append({
        "key": "ladder_half", "label": "阶梯过半",
        "reached": stage_info["total_stages"] > 1 and stage_info["stage"] >= half,
    })
    rows.append({
        "key": f"guard_{GUARD_DAYS}", "label": f"连续 {GUARD_DAYS} 天守住上限",
        "reached": guard_days >= GUARD_DAYS,
    })
    return rows


def compute_journey(
    challenge: object, daily_rows: list[dict[str, object]],
    day_number: int, start_date: date, today: date,
) -> dict[str, object] | None:
    if str(getattr(challenge, "direction", "") or "") != "decrease":
        return None
    reduction = is_cap_mode(challenge) or (is_ladder(challenge) and str(getattr(challenge, "task_type", "")) in ("counter", "timer"))
    base = journey_baseline(challenge)
    stage_info = ladder_stage_info(challenge, max(1, day_number)) if is_ladder(challenge) else None
    guard = trailing_guard_days(daily_rows, challenge, start_date) if reduction else 0
    block: dict[str, object] = {
        "mode": "reduction" if reduction else "quit",
        "unit": str(getattr(challenge, "unit", "") or ""),
        "guard_days": guard,
    }
    if reduction and base > 0:
        avoided, reached = cumulative_avoided(daily_rows, base)
        avg = recent_average(daily_rows)
        block.update({
            "baseline": base,
            "records_days": sum(1 for r in daily_rows if int(r.get("checkin_count", 0) or 0)),
            "cigarettes_avoided": avoided,
            "money_saved": round(avoided * MONEY_PER_UNIT),
            "money_note": MONEY_NOTE,
            "recent_avg": avg,
            "reduction_pct": reduction_pct(base, avg),
        })
        milestones = milestone_rows(reached, stage_info or {"stage": 1, "total_stages": 1}, guard)
    else:
        block["quit_days"] = max(0, (today - start_date).days)
        milestones = milestone_rows(set(), {"stage": 1, "total_stages": 1}, 0)
    if stage_info is not None:
        goal_day = _ladder_goal_day_number(challenge)
        goal_date = start_date + timedelta(days=goal_day - 1)
        from app.services.graduation_service import graduation_block
        grad = graduation_block(challenge, max(1, day_number), start_date, today)
        block.update({
            "ladder_stage": stage_info["stage"],
            "ladder_total_stages": stage_info["total_stages"],
            "days_to_goal": max(0, (goal_date - today).days),
            "goal_date": goal_date.isoformat(),
            "adjustments": adjustment_rows(challenge, start_date),
            "graduation": grad,
        })
        if grad and grad.get("state") == "graduated":
            grad_day = date.fromisoformat(str(grad["graduation_date"]))
            block["health"] = health_block(grad_day, "从你阶梯毕业那天起", today)
        else:
            block["health"] = health_block(goal_date, "按你的阶梯计划到达终点后", today)
    else:
        block["health"] = health_block(start_date, "从你开始戒断那天起", today)
    block["milestones"] = milestones
    return block


class JourneyService:
    def __init__(self) -> None:
        self._repo = CheckInRepository()

    async def build(self, session: AsyncSession, challenge: object,
                    day_number: int, start_date: date, today: date,
                    rows: list[dict] | None = None) -> dict[str, object] | None:
        if str(getattr(challenge, "direction", "") or "") != "decrease":
            return None
        if rows is None:
            rows = await self._repo.get_daily_totals(
                session, int(getattr(challenge, "id")),
                start_date.isoformat(), today.isoformat(),
            )
        return compute_journey(challenge, rows, day_number, start_date, today)


def journey_prompt_line(journey: dict[str, object] | None) -> str:
    if not journey:
        return ""
    parts: list[str] = []
    if journey.get("mode") == "reduction":
        base = journey.get("baseline")
        avoided = journey.get("cigarettes_avoided")
        pct = journey.get("reduction_pct")
        if base and avoided is not None:
            parts.append(f"相比起点（每天约{base:g}），累计已少抽{avoided}，减量幅度约{pct}%")
        stage = journey.get("ladder_stage")
        total = journey.get("ladder_total_stages")
        if stage and total and total > 1:
            parts.append(f"阶梯第{stage}/{total}档")
        guard = journey.get("guard_days")
        if guard:
            parts.append(f"已连续{guard}天守住上限")
    else:
        days = journey.get("quit_days")
        if days is not None:
            parts.append(f"已坚持戒断{days}天")
    if not parts:
        return ""
    return "\n减量旅程：" + "，".join(parts)
