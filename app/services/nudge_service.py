from __future__ import annotations


class NudgeService:
    def evaluate(
        self, challenge: object, today_total: float, today_target: float,
        is_soft_exceeded: bool = False, hour: int = 0,
    ) -> tuple[int, str]:
        direction = str(getattr(challenge, "direction", "") or "increase")
        unit = str(getattr(challenge, "unit", "") or "")
        total = max(0.0, float(today_total))
        target = max(0.0, float(today_target))
        if target <= 0 or total <= 0:
            return 0, ""
        if direction == "decrease":
            return self._decrease(challenge, total, target, unit, hour)
        return self._increase(challenge, total, target, unit, hour, is_soft_exceeded)

    def _decrease(self, challenge: object, total: float, target: float, unit: str, hour: int) -> tuple[int, str]:
        if total > target:
            if str(getattr(challenge, "goal_rule", "") or "") == "ladder":
                return 2, f"今天已{total:.0f}{unit}，量到顶了。先歇一歇，明天配额会自动更低"
            return 2, f"今天已{total:.0f}{unit}，超过目标了。先喝口水停一停，身体比目标重要"
        remaining = target - total
        if 0 < remaining <= 2:
            return 1, f"今天还剩{remaining:.0f}{unit}的量，留到更需要的时刻"
        if hour >= 10:
            elapsed = max(1, hour - 6)
            projected = total * 18 / elapsed
            if projected > target + 0.5:
                return 1, f"按现在的节奏，今天会到{projected:.0f}{unit}。让下一根的间隔再长一点"
        return 0, ""

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