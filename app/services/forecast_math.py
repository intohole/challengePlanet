from __future__ import annotations

DAY_START = 6
DAY_END = 24
WINDOW_MIN_WEIGHT = 0.06
WINDOW_SPREAD = 0.6


def hour_profile(rows: list[dict[str, object]] | None) -> dict[int, float]:
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


def fmt_hour(hours_float: float) -> str:
    h = int(hours_float)
    m = int(round((hours_float - h) * 60))
    if m >= 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def blend_profile(
    all_rows: list[dict[str, object]] | None,
    wd_rows: list[dict[str, object]] | None,
) -> dict[int, float]:
    all_p = hour_profile(all_rows)
    wd_p = hour_profile(wd_rows)
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


def confidence_of(hour_dist: list[dict[str, object]] | None) -> tuple[float, str]:
    active = sum(1 for r in hour_dist or [] if float(r.get("total_value", 0) or 0) > 0)
    if active >= 10:
        return 0.85, "高"
    if active >= 4:
        return 0.6, "中"
    return 0.35, "低"


def basis_of(conf_label: str, wd_rows: list[dict[str, object]] | None) -> str:
    if wd_rows and any(float(r.get("total_value", 0) or 0) > 0 for r in wd_rows):
        return "按你最近两周的同时段节奏"
    if conf_label == "高":
        return "按你最近两周的节奏"
    if conf_label == "中":
        return "按你最近几天的记录"
    return "记录还少，今天先以实际进度为准"


def forward_window(profile: dict[int, float], hour: int) -> tuple[int, int]:
    future = {h: w for h, w in profile.items() if h > hour and w >= WINDOW_MIN_WEIGHT}
    if not future:
        return -1, -1
    peak = max(future, key=lambda h: future[h])
    peak_w = future[peak]
    lo = hi = peak
    while (lo - 1) in future and future[lo - 1] >= peak_w * WINDOW_SPREAD:
        lo -= 1
    while (hi + 1) in future and future[hi + 1] >= peak_w * WINDOW_SPREAD:
        hi += 1
    return lo, hi


def weight_upto(profile: dict[int, float], hour: int) -> float:
    return sum(profile.get(h, 0.0) for h in range(DAY_START, hour))


def project_day_total(today_total: float, hour: int, profile: dict[int, float]) -> float:
    if today_total <= 0:
        return 0.0
    time_frac = min(1.0, max(0.0, float(hour - DAY_START) / (DAY_END - DAY_START)))
    elapsed = weight_upto(profile, hour) if profile else 0.0
    denom = max(elapsed, time_frac)
    if denom <= 0:
        return today_total
    total = sum(profile.get(h, 0.0) for h in range(DAY_START, DAY_END)) if profile else 1.0
    return today_total / denom * (total or 1.0)


def hour_when_reached(
    profile: dict[int, float], hour: int, today_total: float, remaining_units: float,
) -> float | None:
    if remaining_units <= 0 or today_total <= 0:
        return None
    uniform = hour + remaining_units * float(max(1.0, hour - DAY_START)) / today_total
    elapsed = weight_upto(profile, hour) if profile else 0.0
    if elapsed <= 0:
        return uniform
    need = remaining_units / today_total * elapsed
    for h in range(max(DAY_START, hour), DAY_END):
        w = profile.get(h, 0.0)
        if w <= 0:
            continue
        if need <= w:
            return h + need / w
        need -= w
    return uniform


WINDOW_WORDING = {
    "decrease": ("这段对你来说最难", "提前安排点别的"),
    "increase": ("你通常状态最好", "趁那会儿推进"),
}


def window_parts(lo: int, hi: int, direction: str, confidence: float) -> tuple[str, str, str]:
    if lo < 0 or confidence < 0.45:
        return "", "", ""
    span = f"{lo:02d}:00-{hi:02d}:00"
    base, action = WINDOW_WORDING.get(direction, WINDOW_WORDING["increase"])
    return span, base, action


def compose_window_msg(span: str, base: str, action: str, context: str = "") -> str:
    if not span:
        return ""
    ctx = f"，多在「{context}」场景" if context else ""
    return f"{span} {base}{ctx}，{action}"


def fmt_int(value: float) -> str:
    return str(int(round(value)))


CONTEXT_LABELS = {"home": "家", "work": "工作", "social": "社交", "stress": "压力"}
_CONTEXT_MIN_CNT = 3
_CONTEXT_MIN_DAYS = 2
_CONTEXT_RATIO = 1.5


def dominant_context(rows: list[dict[str, object]] | None) -> str:
    if not rows:
        return ""
    best = max(rows, key=lambda r: float(r.get("checkin_count", 0) or 0))
    if float(best.get("checkin_count", 0) or 0) < _CONTEXT_MIN_CNT:
        return ""
    return CONTEXT_LABELS.get(str(best.get("context_tag", "")), "")


def context_pattern(
    rows: list[dict[str, object]] | None, unit: str,
) -> str:
    valid = [(
        CONTEXT_LABELS.get(str(r.get("context_tag", "")), ""),
        float(r.get("total_value", 0) or 0) / max(float(r.get("days", 0) or 0), 1.0),
    ) for r in rows or [] if int(r.get("days", 0) or 0) >= _CONTEXT_MIN_DAYS]
    valid = [v for v in valid if v[0]]
    if len(valid) < 2:
        return ""
    hi = max(valid, key=lambda v: v[1])
    lo = min(valid, key=lambda v: v[1])
    if lo[1] <= 0 or hi[1] / lo[1] < _CONTEXT_RATIO:
        return ""
    return f"「{hi[0]}」时你平均每天 {fmt_int(hi[1])}{unit}，是「{lo[0]}」的 {fmt_int(hi[1] / lo[1])} 倍"
