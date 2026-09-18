from __future__ import annotations


def _hour_profile(rows: list[dict[str, object]] | None) -> dict[int, float]:
    raw: dict[int, float] = {}
    for row in rows or []:
        h = int(row.get("hour", -1))
        v = float(row.get("total_value", 0) or 0)
        if 6 <= h <= 23 and v > 0:
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


class NudgeService:
    def evaluate(
        self, challenge: object, today_total: float, today_target: float,
        hour: int, hour_dist: list[dict[str, object]] | None = None,
        is_soft_exceeded: bool = False,
    ) -> dict[str, object]:
        if str(getattr(challenge, "direction", "") or "increase") == "decrease":
            return self._decrease_forecast(challenge, today_total, today_target, hour, hour_dist)
        return self._increase_forecast(challenge, today_total, today_target, hour, is_soft_exceeded)

    def _decrease_forecast(
        self, challenge: object, today_total: float, today_target: float,
        hour: int, hour_dist: list[dict[str, object]] | None,
    ) -> dict[str, object]:
        unit = str(getattr(challenge, "unit", "") or "")
        if today_total <= 0 or today_target <= 0:
            return self._empty()
        profile = _hour_profile(hour_dist)
        time_frac = min(1.0, max(0.0, float(hour - 6) / 18.0))
        if profile:
            w_elapsed = sum(profile.get(h, 0.0) for h in range(6, hour))
            w_total = sum(profile.get(h, 0.0) for h in range(6, 24))
            denom = max(w_elapsed, time_frac)
            projected = today_total / denom * w_total if denom > 0 else today_total
        else:
            gone = float(max(0.0, hour - 6))
            projected = today_total * 18.0 / gone if gone > 0 else today_total
        remaining_units = max(0.0, today_target - today_total)
        touch_at = ""
        remaining_hours = 0.0
        if remaining_units > 0:
            gone = float(max(1.0, hour - 6))
            need_hours = remaining_units * gone / today_total
            touch_float = hour + need_hours
            if touch_float < 24:
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
            "touch_at": touch_at, "remaining_hours": remaining_hours,
            "remaining_units": round(remaining_units, 1),
            "risk_level": risk, "coach_nudge": coach, "nudge_level": risk,
        }

    def _increase_forecast(
        self, challenge: object, today_total: float, today_target: float,
        hour: int, is_soft_exceeded: bool,
    ) -> dict[str, object]:
        unit = str(getattr(challenge, "unit", "") or "")
        if today_target <= 0:
            return self._empty()
        level, msg = self._increase(challenge, today_total, today_target, unit, hour, is_soft_exceeded)
        return {
            "enabled": True, "projected": 0.0, "touch_at": "", "remaining_hours": 0.0,
            "remaining_units": max(0.0, today_target - today_total),
            "risk_level": 0, "coach_nudge": msg, "nudge_level": level,
        }

    def _empty(self) -> dict[str, object]:
        return {
            "enabled": False, "projected": 0.0, "touch_at": "", "remaining_hours": 0.0,
            "remaining_units": 0.0, "risk_level": 0, "coach_nudge": "", "nudge_level": 0,
        }

    def _decrease_text(
        self, risk: int, total: float, target: float, projected: float,
        touch_at: str, unit: str,
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
        self, challenge: object, total: float, target: float, unit: str,
        hour: int, is_soft_exceeded: bool,
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
