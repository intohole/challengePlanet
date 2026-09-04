from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.checkin_repository import CheckInRepository
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import calc_streak, today_str


class ReportCalculator:
    def __init__(self) -> None:
        self._checkin_repo = CheckInRepository()

    def calc_hourly_items(
        self, rows: list[dict[str, object]], slot_target: float,
    ) -> tuple[list[dict[str, object]], int, float]:
        items: list[dict[str, object]] = []
        peak_hour = -1
        peak_value = 0.0
        for h in range(24):
            row = next((r for r in rows if r["hour"] == h), None)
            total = float(row["total_value"]) if row else 0.0
            cnt = int(row["checkin_count"]) if row else 0
            exceed_pct = (total / slot_target * 100) if slot_target > 0 else 0.0
            items.append({
                "hour": h, "total_value": total, "checkin_count": cnt,
                "target_value": slot_target, "exceed_pct": round(exceed_pct, 1),
            })
            if total > peak_value:
                peak_value = total
                peak_hour = h
        return items, peak_hour, peak_value

    def calc_trend_direction(
        self, points: list[dict[str, object]], direction: str,
    ) -> str:
        if len(points) < 7:
            return "stable"
        half = len(points) // 2
        first_half = sum(p["value"] for p in points[:half]) / max(half, 1)
        second_half = sum(p["value"] for p in points[half:]) / max(len(points) - half, 1)
        diff_pct = (second_half - first_half) / max(first_half, 1.0) * 100
        if direction == "decrease":
            if diff_pct < -5:
                return "improving"
            if diff_pct > 5:
                return "worsening"
        else:
            if diff_pct > 5:
                return "improving"
            if diff_pct < -5:
                return "worsening"
        return "stable"

    def calc_heatmap_levels(
        self, row_map: dict[str, dict[str, object]], challenge,
        start_dt: datetime, end_dt: datetime,
    ) -> tuple[list[dict[str, object]], int, int]:
        cells: list[dict[str, object]] = []
        active_days = 0
        on_track_days = 0
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
                on_track, level = self._calc_day_level(value, target, challenge.direction)
                if on_track:
                    on_track_days += 1
            cells.append({
                "date": ds, "value": value, "target": target,
                "checkin_count": cnt, "level": level,
            })
            cursor += timedelta(days=1)
        return cells, active_days, on_track_days

    def _calc_day_level(
        self, value: float, target: float, direction: str,
    ) -> tuple[bool, int]:
        if direction == "decrease":
            if value <= target:
                return True, 4
            if value <= target * 1.2:
                return False, 3
            if value <= target * 1.5:
                return False, 2
            return False, 1
        if value >= target:
            return True, 4
        if value >= target * 0.8:
            return False, 3
        if value >= target * 0.5:
            return False, 2
        return False, 1

    def calc_completion_stats(
        self, rows: list[dict[str, object]], challenge,
    ) -> tuple[int, int, int]:
        on_track = 0
        soft_exceed = 0
        hard_exceed = 0
        for row in rows:
            value = float(row["value"])
            target = float(row["target"]) if row["target"] else challenge.target_value
            if target <= 0:
                on_track += 1
                continue
            ok, soft, hard = self._calc_completion_day(value, target, challenge)
            on_track += ok
            soft_exceed += soft
            hard_exceed += hard
        return on_track, soft_exceed, hard_exceed

    def _calc_completion_day(
        self, value: float, target: float, challenge,
    ) -> tuple[int, int, int]:
        if challenge.direction == "decrease":
            if value <= target:
                return 1, 0, 0
            if challenge.goal_type == "soft":
                return 0, 1, 0
            return 0, 0, 1
        if value >= target:
            return 1, 0, 0
        if challenge.goal_type == "soft":
            return 0, 1, 0
        return 0, 0, 1

    async def calc_overview_stats(
        self, session: AsyncSession, challenge_id: int, challenge,
    ) -> dict[str, object]:
        today = today_str()
        today_total = await self._checkin_repo.sum_value_by_date(session, challenge_id, today)
        recent_7d = await self._checkin_repo.list_recent(session, challenge_id, days=7)
        daily_7d = self._aggregate_daily(recent_7d)
        last_7d_total = sum(daily_7d.values())
        last_7d_avg = last_7d_total / max(len(daily_7d), 1)

        recent_30d = await self._checkin_repo.list_recent(session, challenge_id, days=30)
        daily_30d = self._aggregate_daily(recent_30d)
        last_30d_avg = sum(daily_30d.values()) / max(len(daily_30d), 1)

        active_days = await self._checkin_repo.count_active_days(session, challenge_id)
        total_checkins = await self._checkin_repo.count_by_challenge(session, challenge_id)

        valid = await load_valid_dates(session, challenge_id)
        streak = calc_streak(valid, today)

        start_dt = now_china() - timedelta(days=6)
        hourly_rows = await self._checkin_repo.get_hourly_distribution(
            session, challenge_id, start_dt.strftime("%Y-%m-%d"), today
        )
        peak_hour, peak_value, best_hour, worst_hour = self._calc_hour_extremes(
            hourly_rows, challenge.direction
        )

        dynamic_baseline = self._calc_dynamic_baseline(last_7d_avg, challenge)
        return {
            "today_total": today_total,
            "last_7d_avg": round(last_7d_avg, 2),
            "last_7d_total": round(last_7d_total, 2),
            "last_30d_avg": round(last_30d_avg, 2),
            "active_days": active_days,
            "total_checkins": total_checkins,
            "streak": streak,
            "peak_hour": peak_hour,
            "peak_value": peak_value,
            "best_hour": best_hour,
            "worst_hour": worst_hour,
            "dynamic_baseline": round(dynamic_baseline, 2),
        }

    def _aggregate_daily(self, checkins: list) -> dict[str, float]:
        daily: dict[str, float] = {}
        for c in checkins:
            daily[c.date] = daily.get(c.date, 0.0) + c.value
        return daily

    def _calc_hour_extremes(
        self, rows: list[dict[str, object]], direction: str,
    ) -> tuple[int, float, int, int]:
        peak_hour = -1
        peak_value = 0.0
        best_hour = -1
        best_value = -1.0
        worst_hour = -1
        worst_value = float("inf")
        for row in rows:
            v = float(row["total_value"])
            if direction == "decrease":
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
        return peak_hour, peak_value, best_hour, worst_hour

    def _calc_dynamic_baseline(self, last_7d_avg: float, challenge) -> float:
        baseline = last_7d_avg * (0.9 if challenge.direction == "decrease" else 1.1)
        return max(baseline, max(challenge.target_value * 0.5, 1.0))

    async def calc_baseline_at(
        self, session: AsyncSession, challenge, date_str: str,
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
        daily = self._aggregate_daily(recent)
        if not daily:
            return max(challenge.target_value, 1.0)
        avg = sum(daily.values()) / len(daily)
        if challenge.direction == "decrease":
            return max(avg * 0.9, max(challenge.target_value * 0.5, 1.0))
        return max(avg * 1.1, 1.0)
