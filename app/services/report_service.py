from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.repositories.sub_goal_repository import SubGoalRepository
from app.services.ai_service import AIService
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import calc_streak, today_str


class ReportService:
    def __init__(self) -> None:
        self._challenge_repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._sub_goal_repo = SubGoalRepository()
        self._insight_repo = InsightRepository()
        self._ai = AIService()

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
        end_date = today_str()
        start_dt = datetime.now() - timedelta(days=days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")

        rows = await self._checkin_repo.get_hourly_distribution(
            session, challenge_id, start_date, end_date
        )
        items: list[dict[str, object]] = []
        for h in range(24):
            row = next((r for r in rows if r["hour"] == h), None)
            total = float(row["total_value"]) if row else 0.0
            cnt = int(row["checkin_count"]) if row else 0
            target = challenge.slot_target_value if challenge.decompose_mode == "time_slot" else 0.0
            exceed_pct = (total / target * 100) if target > 0 else 0.0
            items.append({
                "hour": h,
                "total_value": total,
                "checkin_count": cnt,
                "target_value": target,
                "exceed_pct": round(exceed_pct, 1),
            })

        peak_hour = -1
        peak_value = 0.0
        for item in items:
            if item["total_value"] > peak_value:
                peak_value = item["total_value"]
                peak_hour = item["hour"]

        insight = ""
        if peak_hour >= 0 and peak_value > 0:
            if challenge.direction == "decrease":
                insight = f"你在{peak_hour:02d}:00-{peak_hour + 1:02d}:00这个时段记录最多，这可能是你最容易想{challenge.title}的时段"
            else:
                insight = f"你在{peak_hour:02d}:00-{peak_hour + 1:02d}:00这个时段记录最频繁，这是你的高效时段"

        return {
            "challenge_id": challenge_id,
            "date_range": f"{days}d",
            "direction": challenge.direction,
            "unit": challenge.unit,
            "items": items,
            "peak_hour": peak_hour,
            "peak_value": peak_value,
            "insight": insight,
        }

    async def get_trend(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        days: int = 30,
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        end_date = today_str()
        start_dt = datetime.now() - timedelta(days=days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")

        rows = await self._checkin_repo.get_daily_totals(
            session, challenge_id, start_date, end_date
        )
        row_map: dict[str, dict[str, object]] = {r["date"]: r for r in rows}

        points: list[dict[str, object]] = []
        for i in range(days):
            dt = (start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
            row = row_map.get(dt)
            value = float(row["value"]) if row else 0.0
            cnt = int(row["checkin_count"]) if row else 0
            target = float(row["target"]) if row and row["target"] else challenge.target_value
            baseline = await self._baseline_at(session, challenge, dt)
            points.append({
                "date": dt,
                "value": value,
                "target": target,
                "baseline": baseline,
                "checkin_count": cnt,
            })

        active_values = [p["value"] for p in points if p["checkin_count"] > 0]
        avg_value = sum(active_values) / len(active_values) if active_values else 0.0

        trend_direction = "stable"
        if len(points) >= 7:
            half = len(points) // 2
            first_half = sum(p["value"] for p in points[:half]) / max(half, 1)
            second_half = sum(p["value"] for p in points[half:]) / max(len(points) - half, 1)
            diff_pct = (second_half - first_half) / max(first_half, 1.0) * 100
            if challenge.direction == "decrease":
                if diff_pct < -5:
                    trend_direction = "improving"
                elif diff_pct > 5:
                    trend_direction = "worsening"
            else:
                if diff_pct > 5:
                    trend_direction = "improving"
                elif diff_pct < -5:
                    trend_direction = "worsening"

        insight = ""
        if trend_direction == "improving":
            insight = "你最近的表现比前段时间更好，继续保持这个节奏"
        elif trend_direction == "worsening":
            if challenge.direction == "decrease":
                insight = "最近几天的记录比之前多了一些，我们一起看看发生了什么变化"
            else:
                insight = "最近几天的记录比之前少了一些，要不要调整一下目标？"

        return {
            "challenge_id": challenge_id,
            "granularity": "daily",
            "direction": challenge.direction,
            "unit": challenge.unit,
            "points": points,
            "avg_value": round(avg_value, 2),
            "trend_direction": trend_direction,
            "insight": insight,
        }

    async def _baseline_at(
        self, session: AsyncSession, challenge, date_str: str
    ) -> float:
        target_dt = datetime.strptime(date_str, "%Y-%m-%d")
        cutoff = target_dt - timedelta(days=7)
        recent = await self._checkin_repo.list_by_date_range(
            session, challenge.id,
            cutoff.strftime("%Y-%m-%d"),
            (target_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        if not recent:
            return max(challenge.target_value, 1.0)
        daily: dict[str, float] = {}
        for c in recent:
            daily[c.date] = daily.get(c.date, 0.0) + c.value
        if not daily:
            return max(challenge.target_value, 1.0)
        avg = sum(daily.values()) / len(daily)
        if challenge.direction == "decrease":
            return max(avg * 0.9, max(challenge.target_value * 0.5, 1.0))
        return max(avg * 1.1, 1.0)

    async def get_heatmap(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        year: int | None = None,
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        today = today_str()
        target_year = year or datetime.now().year
        start_date = f"{target_year}-01-01"
        end_date = f"{target_year}-12-31"
        if target_year == datetime.now().year:
            end_date = today

        rows = await self._checkin_repo.get_daily_totals(
            session, challenge_id, start_date, end_date
        )
        row_map: dict[str, dict[str, object]] = {r["date"]: r for r in rows}

        cells: list[dict[str, object]] = []
        active_days = 0
        on_track_days = 0
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        cursor = start_dt
        while cursor <= end_dt:
            ds = cursor.strftime("%Y-%m-%d")
            row = row_map.get(ds)
            value = float(row["value"]) if row else 0.0
            cnt = int(row["checkin_count"]) if row else 0
            target = float(row["target"]) if row and row["target"] else challenge.target_value
            level = 0
            if cnt > 0:
                active_days += 1
                if challenge.direction == "decrease":
                    if value <= target:
                        on_track_days += 1
                        level = 4
                    elif value <= target * 1.2:
                        level = 3
                    elif value <= target * 1.5:
                        level = 2
                    else:
                        level = 1
                else:
                    if value >= target:
                        on_track_days += 1
                        level = 4
                    elif value >= target * 0.8:
                        level = 3
                    elif value >= target * 0.5:
                        level = 2
                    else:
                        level = 1
            cells.append({
                "date": ds, "value": value, "target": target,
                "checkin_count": cnt, "level": level,
            })
            cursor += timedelta(days=1)

        return {
            "challenge_id": challenge_id,
            "year": target_year,
            "direction": challenge.direction,
            "unit": challenge.unit,
            "cells": cells,
            "total_days": (end_dt - start_dt).days + 1,
            "active_days": active_days,
            "on_track_days": on_track_days,
        }

    async def get_completion_rate(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        period: str = "week",
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        today = today_str()
        days = 7 if period == "week" else 30
        start_dt = datetime.now() - timedelta(days=days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")

        rows = await self._checkin_repo.get_daily_totals(
            session, challenge_id, start_date, today
        )
        on_track = 0
        soft_exceed = 0
        hard_exceed = 0
        for row in rows:
            value = float(row["value"])
            target = float(row["target"]) if row["target"] else challenge.target_value
            if target <= 0:
                on_track += 1
                continue
            if challenge.direction == "decrease":
                if value <= target:
                    on_track += 1
                elif challenge.goal_type == "soft":
                    soft_exceed += 1
                else:
                    hard_exceed += 1
            else:
                if value >= target:
                    on_track += 1
                elif challenge.goal_type == "soft":
                    soft_exceed += 1
                else:
                    hard_exceed += 1

        total = len(rows)
        rate = (on_track / total * 100) if total > 0 else 0.0

        insight = ""
        if total > 0:
            if rate >= 80:
                insight = "你最近的坚持很稳定，给你点赞"
            elif rate >= 50:
                if challenge.direction == "decrease":
                    insight = "你已经在很多时段做到了，我们一起看看怎么把其他时段也搞定"
                else:
                    insight = "已经有不少天达成了，继续加油"
            else:
                insight = "最近有些辛苦，要不要把目标调宽松一些？"

        return {
            "challenge_id": challenge_id,
            "period": period,
            "direction": challenge.direction,
            "unit": challenge.unit,
            "on_track_days": on_track,
            "total_days": total,
            "completion_rate": round(rate, 1),
            "soft_exceed_days": soft_exceed,
            "hard_exceed_days": hard_exceed,
            "insight": insight,
        }

    async def get_overview(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        today = today_str()

        today_total = await self._checkin_repo.sum_value_by_date(session, challenge_id, today)
        today_checkins = await self._checkin_repo.list_by_date(session, challenge_id, today)

        recent_7d = await self._checkin_repo.list_recent(session, challenge_id, days=7)
        daily_7d: dict[str, float] = {}
        for c in recent_7d:
            daily_7d[c.date] = daily_7d.get(c.date, 0.0) + c.value
        last_7d_total = sum(daily_7d.values())
        last_7d_avg = last_7d_total / max(len(daily_7d), 1)

        recent_30d = await self._checkin_repo.list_recent(session, challenge_id, days=30)
        daily_30d: dict[str, float] = {}
        for c in recent_30d:
            daily_30d[c.date] = daily_30d.get(c.date, 0.0) + c.value
        last_30d_avg = sum(daily_30d.values()) / max(len(daily_30d), 1)

        active_days = await self._checkin_repo.count_active_days(session, challenge_id)
        total_checkins = await self._checkin_repo.count_by_challenge(session, challenge_id)

        valid = await load_valid_dates(session, challenge_id)
        streak = calc_streak(valid, today)

        end_date = today
        start_dt = datetime.now() - timedelta(days=6)
        hourly_rows = await self._checkin_repo.get_hourly_distribution(
            session, challenge_id, start_dt.strftime("%Y-%m-%d"), end_date
        )
        best_hour = -1
        best_value = -1.0
        worst_hour = -1
        worst_value = float("inf")
        peak_hour = -1
        peak_value = 0.0
        for row in hourly_rows:
            v = float(row["total_value"])
            if challenge.direction == "decrease":
                if v > 0 and v < worst_value:
                    worst_value = v
                    worst_hour = int(row["hour"])
                if v > peak_value:
                    peak_value = v
                    peak_hour = int(row["hour"])
            else:
                if v > best_value:
                    best_value = v
                    best_hour = int(row["hour"])
                if v > peak_value:
                    peak_value = v
                    peak_hour = int(row["hour"])

        dynamic_baseline = last_7d_avg * (0.9 if challenge.direction == "decrease" else 1.1)
        dynamic_baseline = max(dynamic_baseline, max(challenge.target_value * 0.5, 1.0))

        insight = ""
        if challenge.direction == "decrease":
            if last_7d_avg < last_30d_avg:
                insight = f"最近7天平均{last_7d_avg:.1f}{challenge.unit}，比30天均值更低，你正在进步"
            elif peak_hour >= 0:
                insight = f"你在{peak_hour:02d}:00-{peak_hour + 1:02d}:00记录最多，这可能是你的高风险时段"
        else:
            if last_7d_avg > last_30d_avg:
                insight = f"最近7天平均{last_7d_avg:.1f}{challenge.unit}，比30天均值更高，状态不错"
            elif best_hour >= 0:
                insight = f"你在{best_hour:02d}:00-{best_hour + 1:02d}:00表现最好"

        return {
            "challenge_id": challenge_id,
            "challenge_title": challenge.title,
            "direction": challenge.direction,
            "unit": challenge.unit,
            "today_total": today_total,
            "today_target": challenge.target_value,
            "dynamic_baseline": round(dynamic_baseline, 2),
            "streak": streak,
            "total_checkins": total_checkins,
            "active_days": active_days,
            "last_7d_avg": round(last_7d_avg, 2),
            "last_7d_total": round(last_7d_total, 2),
            "last_30d_avg": round(last_30d_avg, 2),
            "best_hour": best_hour if challenge.direction == "increase" else -1,
            "worst_hour": worst_hour if challenge.direction == "decrease" and worst_value != float("inf") else -1,
            "peak_hour": peak_hour,
            "generated_at": datetime.now(),
            "insight": insight,
        }

    async def get_today_checkins_with_sub_goals(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object]:
        challenge = await self._get_challenge(session, challenge_id, user_id)
        today = today_str()
        today_checkins = await self._checkin_repo.list_by_date(session, challenge_id, today)
        today_total = await self._checkin_repo.sum_value_by_date(session, challenge_id, today)

        sub_goals = await self._sub_goal_repo.get_by_challenge(session, challenge_id)
        sub_goal_list: list[dict[str, object]] = []
        for sg in sub_goals:
            today_value = await self._checkin_repo.sum_value_by_sub_goal(session, sg.id, today)
            today_cnt_list = await self._checkin_repo.list_by_sub_goal(session, sg.id, today)
            target = sg.target_value if sg.target_value > 0 else challenge.slot_target_value
            pct = (today_value / target * 100) if target > 0 else 0.0
            sub_goal_list.append({
                "id": sg.id,
                "title": sg.title,
                "time_window_start": sg.time_window_start,
                "time_window_end": sg.time_window_end,
                "target_value": target,
                "goal_type": sg.goal_type,
                "weight": sg.weight,
                "today_value": today_value,
                "today_checkin_count": len(today_cnt_list),
                "progress_pct": round(min(pct, 100.0), 1),
                "is_active": sg.is_active,
            })

        valid = await load_valid_dates(session, challenge_id)
        streak = calc_streak(valid, today)

        return {
            "challenge_id": challenge_id,
            "today": today,
            "today_total": today_total,
            "today_target": challenge.target_value,
            "direction": challenge.direction,
            "unit": challenge.unit,
            "goal_type": challenge.goal_type,
            "decompose_mode": challenge.decompose_mode,
            "streak": streak,
            "today_checkins": [
                {
                    "id": c.id,
                    "timestamp": c.timestamp.isoformat(),
                    "value": c.value,
                    "sub_goal_id": c.sub_goal_id,
                    "mood": c.mood,
                    "reflection": c.reflection,
                    "context_tag": c.context_tag,
                    "ai_feedback": c.ai_feedback,
                }
                for c in today_checkins
            ],
            "sub_goals": sub_goal_list,
        }
