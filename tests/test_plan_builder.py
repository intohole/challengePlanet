#!/usr/bin/env python3
"""plan_builder 确定性计划生成器单测：目标/难度梯度/里程碑/ladder递减"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

src = pathlib.Path(__file__).resolve().parent.parent / "app" / "services" / "plan_builder.py"
spec = importlib.util.spec_from_file_location("plan_builder", src)
pb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pb)

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


# 1. counter 固定目标：每日 target 一致、难度递增、末日里程碑
r = pb.build_plan("每天阅读30页", 30, task_type="counter", target_value=30.0, unit="页")
plan = r["plan"]
check("计划天数=30", len(plan) == 30)
check("第1天 target=30页", plan[0]["target_value"] == 30.0 and plan[0]["unit"] == "页")
check("第15天 target=30页", plan[14]["target_value"] == 30.0)
check("难度梯度递增", plan[0]["difficulty"] < plan[14]["difficulty"] < 6)
check("里程碑日 7 为阶段小结", plan[6]["title"].startswith("阶段小结"))
check("末日为阶段小结", plan[29]["title"].startswith("阶段小结"))
check("每天有 description/tip", all(d.get("description") and d.get("tip") for d in plan[:3]))
check("suggestions 3条", len(r["suggestions"]) == 3)

# 2. 戒烟 ladder 递减 20→0: 第1天20、逐日减、第21天=0、之后保持0
r2 = pb.build_plan("戒烟挑战", 42, task_type="counter", direction="decrease",
                   goal_rule="ladder", ladder_start=20.0, ladder_goal=0.0,
                   ladder_interval=1, ladder_step=1.0, unit="根", steps=["想抽时，先点一下记录这一根"])
p2 = r2["plan"]
check("ladder 第1天上限20", p2[0]["target_value"] == 20.0)
check("ladder 第2天上限19", p2[1]["target_value"] == 19.0)
check("ladder 第21天=0", p2[20]["target_value"] == 0.0)
check("ladder 第42天=0", p2[41]["target_value"] == 0.0)
check("ladder 不出现负值", all(d["target_value"] >= 0 for d in p2))
check("steps 透传到每天", p2[0]["steps"] == ["想抽时，先点一下记录这一根"])

# 3. binary / text: 目标=0
r3 = pb.build_plan("不熬夜", 21, task_type="binary")
check("binary 每天 target=0", all(d["target_value"] == 0 for d in r3["plan"]))
r4 = pb.build_plan("感恩日记", 21, task_type="text")
check("text 每天 target=0", all(d["target_value"] == 0 for d in r4["plan"]))

# 4. ladder increase: 从2到8
r5 = pb.build_plan("跑步", 42, task_type="counter", direction="increase",
                   goal_rule="ladder", ladder_start=2.0, ladder_goal=8.0,
                   ladder_interval=7, ladder_step=1.0, unit="公里")
p5 = r5["plan"]
check("递增 ladder 第1天=2", p5[0]["target_value"] == 2.0)
check("递增 ladder 第8天=3", p5[7]["target_value"] == 3.0)
check("递增 ladder 封顶=8", all(d["target_value"] <= 8.0 for d in p5))

print("\n=== 结果 ===")
for f in failed:
    print("  FAILED:", f)
print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
raise SystemExit(1 if failed else 0)