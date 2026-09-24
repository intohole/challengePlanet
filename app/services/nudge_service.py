from __future__ import annotations

from app.services.forecast_math import (
    DAY_END,
    basis_of,
    blend_profile,
    compose_window_msg,
    confidence_of,
    fmt_hour,
    fmt_int,
    forward_window,
    hour_when_reached,
    project_day_total,
    window_parts,
)
from app.services.goal_rule_service import is_ladder, ladder_cap


class NudgeService:
    def evaluate(
        self,
        challenge: object,
        today_total: float,
        today_target: float,
        hour: int,
        hour_dist: list[dict[str, object]] | None = None,
        is_soft_exceeded: bool = False,
        weekday_dist: list[dict[str, object]] | None = None,
        day_number: int | None = None,
        recent_avg: float | None = None,
    ) -> dict[str, object]:
        if str(getattr(challenge, "direction", "") or "increase") == "decrease":
            return self._decrease_forecast(
                challenge, today_total, today_target, hour,
                hour_dist, weekday_dist, day_number, recent_avg,
            )
        return self._increase_forecast(
            challenge, today_total, today_target, hour, is_soft_exceeded,
            hour_dist, weekday_dist, day_number, recent_avg,
        )

    def apply_bias(self, forecast: dict[str, object], bias: float | None) -> dict[str, object]:
        if bias is None or not forecast.get("enabled") or float(forecast.get("projected", 0) or 0) <= 0:
            return forecast
        base = float(forecast["projected"])
        forecast["projected"] = round(max(base * 0.6, min(base * 1.4, base + bias)), 1)
        forecast["calibrated"] = True
        forecast["bias"] = round(bias, 1)
        return forecast

    def _decrease_forecast(
        self,
        challenge: object,
        today_total: float,
        today_target: float,
        hour: int,
        hour_dist: list[dict[str, object]] | None,
        weekday_dist: list[dict[str, object]] | None,
        day_number: int | None,
        recent_avg: float | None,
    ) -> dict[str, object]:
        unit = str(getattr(challenge, "unit", "") or "")
        profile = blend_profile(hour_dist, weekday_dist)
        confidence, conf_label = confidence_of(hour_dist)
        lo_w, hi_w = forward_window(profile, hour)
        span, base, action = window_parts(lo_w, hi_w, "decrease", confidence)
        risk_window = span
        window_msg = compose_window_msg(span, base, action)
        if today_total <= 0 or today_target <= 0:
            result = self._empty()
            result["risk_window"] = risk_window
            result["risk_window_msg"] = window_msg
            result["risk_window_hours"] = [lo_w, hi_w] if span else []
            return result
        basis = basis_of(conf_label, weekday_dist)
        projected = project_day_total(today_total, hour, profile)
        remaining_units = max(0.0, today_target - today_total)
        touch_at = ""
        remaining_hours = 0.0
        touch_float = hour_when_reached(profile, hour, today_total, remaining_units)
        if touch_float is not None and touch_float < DAY_END:
            touch_at = fmt_hour(touch_float)
            remaining_hours = max(0.0, round(touch_float - hour, 1))
        if today_total >= today_target:
            risk = 2
        elif projected > today_target:
            risk = 1
        else:
            risk = 0
        coach = self._decrease_text(risk, today_total, today_target, projected, touch_at, unit)
        return {
            "enabled": True, "projected": round(projected, 1),
            "confidence": confidence, "confidence_label": conf_label, "basis": basis,
            "touch_at": touch_at, "remaining_hours": remaining_hours,
            "remaining_units": round(remaining_units, 1),
            "risk_level": risk, "coach_nudge": coach, "nudge_level": risk,
            "reach_at": "", "ladder_outlook": self._ladder_outlook(challenge, day_number, recent_avg),
            "risk_window": risk_window, "risk_window_msg": window_msg,
            "risk_window_hours": [lo_w, hi_w] if span else [],
        }

    def _increase_forecast(
        self,
        challenge: object,
        today_total: float,
        today_target: float,
        hour: int,
        is_soft_exceeded: bool,
        hour_dist: list[dict[str, object]] | None = None,
        weekday_dist: list[dict[str, object]] | None = None,
        day_number: int | None = None,
        recent_avg: float | None = None,
    ) -> dict[str, object]:
        unit = str(getattr(challenge, "unit", "") or "")
        if today_target <= 0:
            return self._empty()
        level, msg = self._increase(challenge, today_total, today_target, unit, hour, is_soft_exceeded)
        profile = blend_profile(hour_dist, weekday_dist)
        confidence, conf_label = confidence_of(hour_dist)
        remaining = max(0.0, today_target - today_total)
        reach_at = ""
        if today_total > 0:
            projected = round(project_day_total(today_total, hour, profile), 1)
            basis = basis_of(conf_label, weekday_dist)
            reach_float = hour_when_reached(profile, hour, today_total, remaining)
            if reach_float is not None and reach_float < DAY_END:
                reach_at = fmt_hour(reach_float)
        else:
            projected = 0.0
            confidence, conf_label = 0.35, "低"
            basis = "今天还没记录，先开始第一步"
        lo_w, hi_w = forward_window(profile, hour)
        span, base, action = window_parts(lo_w, hi_w, "increase", confidence)
        return {
            "enabled": True, "projected": projected,
            "confidence": confidence, "confidence_label": conf_label, "basis": basis,
            "touch_at": "", "remaining_hours": 0.0,
            "remaining_units": round(remaining, 1),
            "risk_level": 0, "coach_nudge": msg, "nudge_level": level,
            "reach_at": reach_at, "ladder_outlook": self._ladder_outlook(challenge, day_number, recent_avg),
            "risk_window": span, "risk_window_msg": compose_window_msg(span, base, action),
            "risk_window_hours": [lo_w, hi_w] if span else [],
        }

    def _empty(self) -> dict[str, object]:
        return {
            "enabled": False, "projected": 0.0,
            "confidence": 0.0, "confidence_label": "", "basis": "",
            "touch_at": "", "remaining_hours": 0.0, "remaining_units": 0.0,
            "risk_level": 0, "coach_nudge": "", "nudge_level": 0,
            "reach_at": "", "ladder_outlook": None,
            "risk_window": "", "risk_window_msg": "", "risk_window_hours": [],
        }

    def _decrease_text(
        self,
        risk: int,
        total: float,
        target: float,
        projected: float,
        touch_at: str,
        unit: str,
    ) -> str:
        if risk >= 2:
            if total > target:
                return f"今天已超 {fmt_int(total - target)}{unit}。停下来，别再继续了"
            return f"今天已到上限 {fmt_int(target)}{unit}，就此打住"
        if risk == 1:
            over = max(1.0, projected - target)
            if touch_at:
                return f"按现在的节奏，今天预计{projected:.0f}{unit}，会超{over:.0f}。下一次推迟到{touch_at}之后"
            return f"按现在的节奏，今天预计{projected:.0f}{unit}，会超{over:.0f}。让间隔再拉长一点"
        return ""

    def _increase(
        self,
        challenge: object,
        total: float,
        target: float,
        unit: str,
        hour: int,
        is_soft_exceeded: bool,
    ) -> tuple[int, str]:
        if total >= target or is_soft_exceeded:
            return 0, ""
        if hour >= 20:
            remaining = target - total
            return 1, f"今天还差{remaining:.0f}{unit}，现在补上，今晚睡得踏实"
        if hour >= 17 and target > 0 and total < target * 0.5:
            remaining = target - total
            return 1, f"今天进度还没过半，还差{remaining:.0f}{unit}，趁现在抓紧就达标了"
        return 0, ""

    def _ladder_outlook(
        self,
        challenge: object,
        day_number: int | None,
        recent_avg: float | None,
    ) -> dict[str, object] | None:
        if not is_ladder(challenge) or recent_avg is None or recent_avg <= 0:
            return None
        unit = str(getattr(challenge, "unit", "") or "")
        duration = max(0, int(getattr(challenge, "duration_days", 0) or 0))
        day = int(day_number or 0)
        remaining = max(0, duration - day)
        caps = [ladder_cap(challenge, d) for d in range(max(1, day - 6), day + 1)]
        plan_cap = sum(caps) / len(caps) if caps else 0.0
        if plan_cap <= 0:
            return None
        if str(getattr(challenge, "direction", "") or "increase") == "decrease":
            on_track = recent_avg <= plan_cap
            if on_track:
                message = f"最近7天平均 {fmt_int(recent_avg)}{unit}，在阶梯计划内"
            else:
                message = f"最近7天平均 {fmt_int(recent_avg)}{unit}，比阶梯计划高 {fmt_int(recent_avg - plan_cap)}{unit}"
        else:
            on_track = recent_avg >= plan_cap
            if on_track:
                message = f"最近7天平均 {fmt_int(recent_avg)}{unit}，在阶梯计划内"
            else:
                message = f"最近7天平均 {fmt_int(recent_avg)}{unit}，比阶梯计划低 {fmt_int(plan_cap - recent_avg)}{unit}"
        return {
            "on_track": on_track, "recent_avg": round(recent_avg, 1),
            "plan_cap": round(plan_cap, 1), "remaining_days": remaining, "message": message,
        }