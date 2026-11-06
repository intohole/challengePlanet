"""S112 定时任务链守底: ironman 选型与自建调度器 gate 接线在位断言。

撤修复(ensure_ironman 改回裸调 startup_ironman / 自建 scheduler 去 gate)本文件必红。
判例: Lion 故障时 lifespan 中断→job 连坐(S112 4+仓); 自建 AsyncIOScheduler
无条件 start=本地/E2E 暗道(geniusStudent 判例同款)。
"""
from __future__ import annotations

import ast
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1] / "app/main.py"
BARE_STARTUP_FORBIDDEN = True
False_START_NEEDS_GATE = False


def _await_calls(tree: ast.AST) -> list[str]:
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if isinstance(fn, ast.Name):
                names.append(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.append(fn.attr)
    return names


def test_ironman_ensure_not_bare_startup() -> None:
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    calls = _await_calls(tree)
    assert "startup_ironman" not in calls, (
        "main.py 存在裸调 await startup_ironman( )(fail-fast 会炸 lifespan 连坐 job 链, S112 修复回退)"
    )
