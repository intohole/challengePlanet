from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.services.report_calculator import ReportCalculator
from app.services.streak_service import today_str


class ReportService:
    def __init__(self) -> None:
        self._challenge_repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._insight_repo = InsightRepository()
        self._calc = ReportCalculator()

    async def _get_challenge(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ):
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return challenge

    async def get_hourly_distribution(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        days: int = 7,
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        start_dt = now_china() - timedelta(days=days - 1)
        rows = await self._checkin_repo.get_hourly_distribution(
            session, challenge_id, start_dt.strftime("%Y-%m-%d"), today_str()
        )
        slot_target = challenge.slot_target_value if challenge.decompose_mode == "time_slot" else 0.0
        items, peak_hour, peak_value = self._calc.calc_hourly_items(rows, slot_target)
        insight = self._hourly_insight(peak_hour, peak_value, challenge)
        return {
            "challenge_id": challenge_id, "date_range": f"{days}d",
            "direction": challenge.direction, "unit": challenge.unit,
            "items": items, "peak_hour": peak_hour,
            "peak_value": peak_value, "insight": insight,
        }

    def _hourly_insight(self, peak_hour: int, peak_value: float, challenge) -> str:
        if peak_hour < 0 or peak_value <= 0:
            return ""
        if challenge.direction == "decrease":
            return f"你在{peak_hour:02d}:00-{peak_hour + 1:02d}:00这个时段记录最多，这可能是你最容易想{challenge.title}的时段"
        return f"你在{peak_hour:02d}:00-{peak_hour + 1:02d}:00这个时段记录最频繁，这是你的高效时段"

    async def get_trend(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        days: int = 30,
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        start_dt = now_china() - timedelta(days=days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")
        rows = await self._checkin_repo.get_daily_totals(session, challenge_id, start_date, today_str())
        row_map = {r["date"]: r for r in rows}
        points: list[dict[str, object]] = []
        for i in range(days):
            dt = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            row = row_map.get(dt)
            value = float(row["value"]) if row else 0.0
            cnt = int(row["checkin_count"]) if row else 0
            target = float(row["target"]) if row and row["target"] else challenge.target_value
            baseline = await self._calc.calc_baseline_at(session, challenge, dt)
            points.append({
                "date": dt, "value": value, "target": target,
                "baseline": baseline, "checkin_count": cnt,
            })
        active_values = [p["value"] for p in points if p["checkin_count"] > 0]
        avg_value = sum(active_values) / len(active_values) if active_values else 0.0
        trend_direction = self._calc.calc_trend_direction(points, challenge.direction)
        insight = self._trend_insight(trend_direction, challenge)
        return {
            "challenge_id": challenge_id, "granularity": "daily",
            "direction": challenge.direction, "unit": challenge.unit,
            "points": points, "avg_value": round(avg_value, 2),
            "trend_direction": trend_direction, "insight": insight,
        }

    def _trend_insight(self, trend_direction: str, challenge) -> str:
        if trend_direction == "improving":
            return "你最近的表现比前段时间更好，继续保持这个节奏"
        if trend_direction == "worsening":
            if challenge.direction == "decrease":
                return "最近几天的记录比之前多了一些，我们一起看看发生了什么变化"
            return "最近几天的记录比之前少了一些，要不要调整一下目标？"
        return ""

    async def get_heatmap(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        year: int | None = None,
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        target_year = year or now_china().year
        start_date = f"{target_year}-01-01"
        end_date = today_str() if target_year == now_china().year else f"{target_year}-12-31"
        rows = await self._checkin_repo.get_daily_totals(session, challenge_id, start_date, end_date)
        row_map = {r["date"]: r for r in rows}
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        cells, active_days, on_track_days = self._calc.calc_heatmap_levels(
            row_map, challenge, start_dt, end_dt
        )
        return {
            "challenge_id": challenge_id, "year": target_year,
            "direction": challenge.direction, "unit": challenge.unit,
            "cells": cells, "total_days": (end_dt - start_dt).days + 1,
            "active_days": active_days, "on_track_days": on_track_days,
        }

    async def get_completion_rate(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        period: str = "week",
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        days = 7 if period == "week" else 30
        start_dt = now_china() - timedelta(days=days - 1)
        rows = await self._checkin_repo.get_daily_totals(
            session, challenge_id, start_dt.strftime("%Y-%m-%d"), today_str()
        )
        on_track, soft_exceed, hard_exceed = self._calc.calc_completion_stats(rows, challenge)
        total = len(rows)
        rate = (on_track / total * 100) if total > 0 else 0.0
        insight = self._completion_insight(rate, total, challenge)
        return {
            "challenge_id": challenge_id, "period": period,
            "direction": challenge.direction, "unit": challenge.unit,
            "on_track_days": on_track, "total_days": total,
            "completion_rate": round(rate, 1),
            "soft_exceed_days": soft_exceed, "hard_exceed_days": hard_exceed,
            "insight": insight,
        }

    def _completion_insight(self, rate: float, total: int, challenge) -> str:
        if total <= 0:
            return ""
        if rate >= 80:
            return "你最近的坚持很稳定，给你点赞"
        if rate >= 50:
            if challenge.direction == "decrease":
                return "你已经在很多时段做到了，我们一起看看怎么把其他时段也搞定"
            return "已经有不少天达成了，继续加油"
        return "最近有些辛苦，要不要把目标调宽松一些？"

    async def get_overview(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        stats = await self._calc.calc_overview_stats(session, challenge_id, challenge)
        insight = self._overview_insight(stats, challenge)
        best_hour = stats["best_hour"] if challenge.direction == "increase" else -1
        worst_hour = stats["worst_hour"] if challenge.direction == "decrease" else -1
        return {
            "challenge_id": challenge_id, "challenge_title": challenge.title,
            "direction": challenge.direction, "unit": challenge.unit,
            "today_total": stats["today_total"],
            "today_target": challenge.target_value,
            "dynamic_baseline": stats["dynamic_baseline"],
            "streak": stats["streak"],
            "total_checkins": stats["total_checkins"],
            "active_days": stats["active_days"],
            "last_7d_avg": stats["last_7d_avg"],
            "last_7d_total": stats["last_7d_total"],
            "last_30d_avg": stats["last_30d_avg"],
            "best_hour": best_hour, "worst_hour": worst_hour,
            "peak_hour": stats["peak_hour"],
            "generated_at": now_china(), "insight": insight,
        }

    def _overview_insight(self, stats: dict[str, object], challenge) -> str:
        last_7d_avg = float(stats["last_7d_avg"])
        last_30d_avg = float(stats["last_30d_avg"])
        peak_hour = int(stats["peak_hour"])
        best_hour = int(stats["best_hour"])
        if challenge.direction == "decrease":
            if last_7d_avg < last_30d_avg:
                return f"最近7天平均{last_7d_avg:.1f}{challenge.unit}，比30天均值更低，你正在进步"
            if peak_hour >= 0:
                return f"你在{peak_hour:02d}:00-{peak_hour + 1:02d}:00记录最多，这可能是你的高风险时段"
        else:
            if last_7d_avg > last_30d_avg:
                return f"最近7天平均{last_7d_avg:.1f}{challenge.unit}，比30天均值更高，状态不错"
            if best_hour >= 0:
                return f"你在{best_hour:02d}:00-{best_hour + 1:02d}:00表现最好"
        return ""
