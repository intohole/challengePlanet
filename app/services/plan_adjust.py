from __future__ import annotations

import re

_REPLACE_RE = re.compile(
    r"(?:改成|改为|每天|降到|降至|减到|减少到|控制在|调整为)\s*(\d+(?:\.\d+)?)\s*(分钟|小时|个|次|页|字|篇|章|公里|步|组|轮|遍|题|词|张|首|支)?"
)
_PERCENT_DOWN_RE = re.compile(r"(?:降低|下调|减少)\s*(\d+(?:\.\d+)?)\s*%")
_PERCENT_UP_RE = re.compile(r"(?:提高|上调|增加)\s*(\d+(?:\.\d+)?)\s*%")


def _norm_num(v: float) -> int | float:
    v = round(v, 1)
    return int(v) if float(v).is_integer() else v


def parse_numeric_op(hint: str) -> dict[str, object] | None:
    text = hint.strip()
    if not text:
        return None
    m = _REPLACE_RE.search(text)
    if m:
        return {"op": "replace", "value": float(m.group(1)), "unit": m.group(2) or ""}
    if re.search(r"减半|减一半|减为一半|砍半", text):
        return {"op": "multiply", "value": 0.5}
    if re.search(r"翻倍|增加一倍|加倍|双倍|乘以2|乘2", text):
        return {"op": "multiply", "value": 2.0}
    if re.search(r"增加一半|加一半|提高一半|1\.5倍", text):
        return {"op": "multiply", "value": 1.5}
    m = _PERCENT_DOWN_RE.search(text)
    if m:
        return {"op": "multiply", "value": 1.0 - float(m.group(1)) / 100.0}
    m = _PERCENT_UP_RE.search(text)
    if m:
        return {"op": "multiply", "value": 1.0 + float(m.group(1)) / 100.0}
    return None


def apply_numeric_adjust(plan: list[dict[str, object]], hint: str) -> list[dict[str, object]]:
    op = parse_numeric_op(hint)
    if op is None:
        return plan
    for day in plan:
        try:
            tv = float(day.get("target_value") or 0)
        except (TypeError, ValueError):
            continue
        if tv <= 0:
            continue
        if op["op"] == "multiply":
            day["target_value"] = _norm_num(tv * float(op["value"]))
        else:
            day["target_value"] = int(op["value"]) if float(op["value"]).is_integer() else op["value"]
            if op.get("unit"):
                day["unit"] = str(op["unit"])
    return plan
