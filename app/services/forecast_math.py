from __future__ import annotations

DAY_START = 6
DAY_END = 24
NIGHT_WRAP_FROM = 20
WINDOW_MIN_WEIGHT = 0.06
WINDOW_SPREAD = 0.6
MIN_ELAPSED = 0.15
MIN_SAMPLE = 2
MIN_PROGRESS = 0.25


def hour_profile(rows: list[dict[str, object]] | None) -> dict[int, float]:
    raw: dict[int, float] = {}
    for row in rows or []:
        h = int(row.get("hour", -1))
        v = float(row.get("total_value", 0) or 0)
        if 0 <= h < DAY_END and v > 0:
            raw[h] = raw.get(h, 0.0) + v
    total = sum(raw.values())
    if total <= 0:
        return {}
    return {h: v / total for h, v in raw.items()}


def display_ready(hour: int, today_count: int, profile: dict[int, float] | None = None) -> bool:
    if hour < DAY_START:
        return False
    return today_count >= MIN_SAMPLE or day_progress(profile, hour) >= MIN_PROGRESS


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
    order = list(range(hour + 1, DAY_END))
    if hour >= NIGHT_WRAP_FROM:
        order += list(range(0, DAY_START))
    weights = {h: profile.get(h, 0.0) for h in order}
    candidates = [i for i, h in enumerate(order) if weights[h] >= WINDOW_MIN_WEIGHT]
    if not candidates:
        return -1, -1
    peak_i = max(candidates, key=lambda i: weights[order[i]])
    peak_w = weights[order[peak_i]]
    lo_i = hi_i = peak_i
    while lo_i - 1 >= 0 and weights[order[lo_i - 1]] >= peak_w * WINDOW_SPREAD:
        lo_i -= 1
    while hi_i + 1 < len(order) and weights[order[hi_i + 1]] >= peak_w * WINDOW_SPREAD:
        hi_i += 1
    return order[lo_i], order[hi_i]


def weight_upto(profile: dict[int, float], hour: int) -> float:
    return sum(profile.get(h, 0.0) for h in range(0, hour))


def day_progress(profile: dict[int, float] | None, hour: int) -> float:
    time_frac = min(1.0, max(0.0, float(hour - DAY_START) / (DAY_END - DAY_START)))
    elapsed = weight_upto(profile, hour) if profile else 0.0
    return max(elapsed, time_frac, MIN_ELAPSED)


def project_day_total(today_total: float, hour: int, profile: dict[int, float]) -> float:
    if today_total <= 0:
        return 0.0
    denom = day_progress(profile, hour)
    total = sum(profile.values()) if profile else 1.0
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


def merge_context_totals(
    first: list[dict[str, object]] | None,
    second: list[dict[str, object]] | None,
) -> list[dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    for row in list(first or []) + list(second or []):
        tag = str(row.get("context_tag", "") or "")
        item = merged.setdefault(
            tag,
            {"context_tag": tag, "total_value": 0.0, "checkin_count": 0, "days": 0},
        )
        item["total_value"] = float(item["total_value"]) + float(row.get("total_value", 0) or 0)
        item["checkin_count"] = int(item["checkin_count"]) + int(row.get("checkin_count", 0) or 0)
        item["days"] = int(item["days"]) + int(row.get("days", 0) or 0)
    return list(merged.values())


WINDOW_WORDING = {
    "decrease": ("这段对你来说最难", "提前安排点别的"),
    "increase": ("你通常状态最好", "趁那会儿推进"),
}


def window_parts(lo: int, hi: int, direction: str, confidence: float) -> tuple[str, str, str]:
    if lo < 0 or confidence < 0.45:
        return "", "", ""
    span = f"{lo:02d}:00" if lo == hi else f"{lo:02d}:00-{hi:02d}:00"
    base, action = WINDOW_WORDING.get(direction, WINDOW_WORDING["increase"])
    return span, base, action


def compose_window_msg(span: str, base: str, action: str, context: str = "") -> str:
    if not span:
        return ""
    ctx = f"，多在「{context}」场景" if context else ""
    return f"{span} {base}{ctx}，{action}"


def fmt_int(value: float) -> str:
    return str(int(round(value)))


CONTEXT_LABELS = {"home": "家", "work": "工作", "social": "社交", "stress": "压力", "drink": "酒后", "meal": "饭后", "bored": "无聊", "habit": "习惯性"}
CONTEXT_TAGS = frozenset({"", "home", "work", "social", "stress", "drink", "meal", "bored", "habit"})
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
