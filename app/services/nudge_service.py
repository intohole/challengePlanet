from __future__ import annotations

from app.services.goal_rule_service import is_ladder

DAY_START = 6
DAY_END = 24


def _hour_profile(rows: list[dict[str, object]] | None) -> dict[int, float]:
    raw: dict[int, float] = {}
    for row in rows or []:
        h = int(row.get("hour", -1))
        v = float(row.get("total_value", 0) or 0)
        if DAY_START <= h < DAY_END and v > 0:
            raw[h] = raw.get(h, 0.0) + v
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {h: v / total for h, v in raw.items()}


def _fmt_hour(hours_float: float) -> str:
    h = int(hours_float)
    m = int(round((hours_float - h) * 60))
    if m >= 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def _blend_profile(
    all_rows: list[dict[str, object]] | None,
    wd_rows: list[dict[str, object]] | None,
) -> dict[int, float]:
    all_p = _hour_profile(all_rows)
    wd_p = _hour_profile(wd_rows)
    if not wd_p:
        return all_p
    wd_active = sum(1 for r in wd_rows or [] if float(r.get("total_value", 0) or 0) > 0)
    w = 0.6 if wd_active >= 3 else 0.3
    hours = set(all_p) | set(wd_p)
    mixed = {h: wd_p.get(h, 0.0) * w + all_p.get(h, 0.0) * (1 - w) for h in hours}
    total = sum(mixed.values())
    if total <= 0:
        return all_p
    return {h: v / total for h, v in mixed.items()}


def _confidence_of(hour_dist: list[dict[str, object]] | None) -> tuple[float, str]:
    active = sum(1 for r in hour_dist or [] if float(r.get("total_value", 0) or 0) > 0)
    if active >= 10:
        return 0.85, "高"
    if active >= 4:
        return 0.6, "中"
    return 0.35, "低"


def _basis_of(conf_label: str, wd_rows: list[dict[str, object]] | None) -> str:
    if wd_rows and any(float(r.get("total_value", 0) or 0) > 0 for r in wd_rows):
        return "按你最近两周的同时段节奏"
    if conf_label == "高":
        return "按你最近两周的节奏"
    if conf_label == "中":
        return "按你最近几天的记录"
    return "记录还少，今天先以实际进度为准"


def _interval(projected: float, confidence: float) -> tuple[float, float]:
    spread = 0.2 if confidence >= 0.7 else (0.3 if confidence >= 0.45 else 0.45)
    return round(projected * (1 - spread), 1), round(projected * (1 + spread), 1)


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
        return self._increase_forecast(challenge, today_total, today_target, hour, is_soft_exceeded)

    def apply_bias(self, forecast: dict[str, object], bias: float | None) -> dict[str, object]:
        if bias is None or not forecast.get("enabled") or float(forecast.get("projected", 0) or 0) <= 0:
            return forecast
        base = float(forecast["projected"])
        adjusted = max(base * 0.6, min(base * 1.4, base + bias))
        forecast["projected"] = round(adjusted, 1)
        lo = float(forecast.get("projected_low", 0) or 0)
        hi = float(forecast.get("projected_high", 0) or 0)
        spread = hi - lo
        forecast["projected_low"] = round(adjusted - spread / 2, 1)
        forecast["projected_high"] = round(adjusted + spread / 2, 1)
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
        if today_total <= 0 or today_target <= 0:
            return self._empty()
        profile = _blend_profile(hour_dist, weekday_dist)
        confidence, conf_label = _confidence_of(hour_dist)
        basis = _basis_of(conf_label, weekday_dist)
        time_frac = min(1.0, max(0.0, float(hour - DAY_START) / (DAY_END - DAY_START)))
        if profile:
            w_elapsed = sum(profile.get(h, 0.0) for h in range(DAY_START, hour))
            w_total = sum(profile.get(h, 0.0) for h in range(DAY_START, DAY_END))
            denom = max(w_elapsed, time_frac)
            projected = today_total / denom * w_total if denom > 0 else today_total
        else:
            gone = float(max(0.0, hour - DAY_START))
            projected = today_total * (DAY_END - DAY_START) / gone if gone > 0 else today_total
        low, high = _interval(projected, confidence)
        remaining_units = max(0.0, today_target - today_total)
        touch_at = ""
        remaining_hours = 0.0
        if remaining_units > 0:
            gone = float(max(1.0, hour - DAY_START))
            need_hours = remaining_units * gone / today_total
            touch_float = hour + need_hours
            if touch_float < DAY_END:
                touch_at = _fmt_hour(touch_float)
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
            "projected_low": low, "projected_high": high,
            "confidence": confidence, "confidence_label": conf_label, "basis": basis,
            "touch_at": touch_at, "remaining_hours": remaining_hours,
            "remaining_units": round(remaining_units, 1),
            "risk_level": risk, "coach_nudge": coach, "nudge_level": risk,
            "reach_at": "", "ladder_outlook": self._ladder_outlook(challenge, day_number, recent_avg),
        }

    def _increase_forecast(
        self,
        challenge: object,
        today_total: float,
        today_target: float,
        hour: int,
        is_soft_exceeded: bool,
    ) -> dict[str, object]:
        unit = str(getattr(challenge, "unit", "") or "")
        if today_target <= 0:
            return self._empty()
        level, msg = self._increase(challenge, today_total, today_target, unit, hour, is_soft_exceeded)
        elapsed = max(1.0, float(hour - DAY_START))
        remaining = max(0.0, today_target - today_total)
        reach_at = ""
        if today_total > 0:
            pace = today_total / elapsed
            projected = round(pace * (DAY_END - DAY_START), 1)
            if remaining > 0:
                reach_float = hour + remaining / pace
                if reach_float < DAY_END:
                    reach_at = _fmt_hour(reach_float)
            confidence, conf_label = 0.6, "中"
            basis = "按你今天的记录速度"
        else:
            projected = 0.0
            confidence, conf_label = 0.35, "低"
            basis = "今天还没记录，先开始第一步"
        low, high = _interval(projected, confidence) if projected > 0 else (0.0, 0.0)
        return {
            "enabled": True, "projected": projected,
            "projected_low": low, "projected_high": high,
            "confidence": confidence, "confidence_label": conf_label, "basis": basis,
            "touch_at": "", "remaining_hours": 0.0,
            "remaining_units": round(remaining, 1),
            "risk_level": 0, "coach_nudge": msg, "nudge_level": level,
            "reach_at": reach_at, "ladder_outlook": None,
        }

    def _empty(self) -> dict[str, object]:
        return {
            "enabled": False, "projected": 0.0, "projected_low": 0.0, "projected_high": 0.0,
            "confidence": 0.0, "confidence_label": "", "basis": "",
            "touch_at": "", "remaining_hours": 0.0, "remaining_units": 0.0,
            "risk_level": 0, "coach_nudge": "", "nudge_level": 0,
            "reach_at": "", "ladder_outlook": None,
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
                return f"今天已{total:.0f}{unit}，超过目标了。身体比目标重要，先喝口水停一停"
            return f"今天已{total:.0f}/{target:.0f}{unit}，到顶了。先停一停，下一次留到更需要的时刻"
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
        goal = float(getattr(challenge, "ladder_goal", 0) or 0)
        unit = str(getattr(challenge, "unit", "") or "")
        duration = max(0, int(getattr(challenge, "duration_days", 0) or 0))
        remaining = max(0, duration - int(day_number or 0))
        on_track = recent_avg <= goal
        if on_track:
            message = f"按现在的水平，结束时能到 {goal:.0f}{unit} 以下"
        else:
            gap = round(recent_avg - goal, 1)
            message = f"按现在的水平，结束时约 {recent_avg:.1f}{unit}，离目标还差 {gap}{unit}"
        return {
            "on_track": on_track, "projected_end": round(recent_avg, 1),
            "goal": goal, "remaining_days": remaining, "message": message,
        }
