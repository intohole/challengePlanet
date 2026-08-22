#!/usr/bin/env python3
from __future__ import annotations

import sys

sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])

from app.services.plan_adjust import parse_numeric_op, apply_numeric_adjust

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def plan() -> list[dict[str, object]]:
    return [
        {"day": i + 1, "title": f"任务{i + 1}", "target_value": 30.0, "unit": "分钟"}
        for i in range(5)
    ]


print("== 数值操作解析 ==")
check("减半", parse_numeric_op("太难了减半") == {"op": "multiply", "value": 0.5}, str(parse_numeric_op("太难了减半")))
check("改成15分钟", (parse_numeric_op("改成15分钟") or {}).get("value") == 15.0, str(parse_numeric_op("改成15分钟")))
check("每分钟改成20", (parse_numeric_op("每天20") or {}).get("value") == 20.0, str(parse_numeric_op("每天20")))
check("下调30%", (parse_numeric_op("下调30%") or {}).get("value") == 0.7, str(parse_numeric_op("下调30%")))
check("提高20%", (parse_numeric_op("提高20%") or {}).get("value") == 1.2, str(parse_numeric_op("提高20%")))
check("翻倍", (parse_numeric_op("任务翻倍") or {}).get("value") == 2.0, str(parse_numeric_op("任务翻倍")))
check("无关指令返回None", parse_numeric_op("保持现状吧") is None, str(parse_numeric_op("保持现状吧")))

print("== 数值应用 ==")
half = apply_numeric_adjust(plan(), "太难了，每天任务减半")
check("减半后全部target=15", all(float(d["target_value"]) == 15.0 for d in half), str([d["target_value"] for d in half]))
exact = apply_numeric_adjust(plan(), "改成15分钟")
check("改成15分钟全部=15", all(float(d["target_value"]) == 15.0 for d in exact), str([d["target_value"] for d in exact]))
check("改成15分钟unit更新", all(d["unit"] == "分钟" for d in exact), str([d["unit"] for d in exact]))
double = apply_numeric_adjust(plan(), "任务翻倍")
check("翻倍后全部=60", all(float(d["target_value"]) == 60.0 for d in double), str([d["target_value"] for d in double]))
none = apply_numeric_adjust(plan(), "保持现状吧")
check("无关指令不动计划", all(float(d["target_value"]) == 30.0 for d in none), str([d["target_value"] for d in none]))
zero = apply_numeric_adjust([{"day": 1, "target_value": 0, "unit": ""}], "改成15")
check("target=0跳过低保0", float(zero[0]["target_value"]) == 0, str(zero[0]["target_value"]))

print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
for name, d in failed:
    print(f"FAILED: {name} :: {d}")
sys.exit(1 if failed else 0)