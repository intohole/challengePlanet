"""task_type 声明纪律全仓守底（r104 收归）。

task_type 是意图路由/thinking 缺省/effort 缺省/档位预算四链总开关；
全仓 AST 扫描防回潮（r96 判例：泛化扫描，禁点名白名单打卡思维）。
"""
import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

# 本仓全部 LLM 出口：nexus ask / stream_ask 直调
TARGET_METHODS = {"ask", "stream_ask"}


def _iter_py_files():
    return [p for p in APP_ROOT.rglob("*.py") if "__pycache__" not in str(p)]


def test_llm_calls_declare_task_type():
    offenders = []
    for path in _iter_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else "")
            if name in TARGET_METHODS:
                kwargs = {kw.arg for kw in node.keywords if kw.arg}
                if "task_type" not in kwargs:
                    offenders.append(f"{path.relative_to(APP_ROOT.parent)}:{node.lineno} {name}() 缺 task_type")
    assert offenders == [], "存在缺 task_type 声明的 LLM 调用点:\n" + "\n".join(offenders)


def test_declared_values_registered():
    """声明值必须全部在 nexus 值域内（17 档+中性值，防未登记值回归）。"""
    registered = {
        "chat", "assistant", "goodbye", "extract", "extraction", "classify", "intent",
        "summarize", "analyze", "evaluation", "code", "creative", "writing", "article",
        "report", "research", "ppt",
        "eval", "rerank", "eval_batch", "vision", "embedding", "json_mode", "tool_calling",
        "simple", "complex", "long_context",
    }
    declared = set()
    for path in _iter_py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else "")
            if name in TARGET_METHODS:
                for kw in node.keywords:
                    if kw.arg == "task_type" and isinstance(kw.value, ast.Constant):
                        declared.add(kw.value.value)
    unknown = declared - registered
    assert unknown == set(), f"未登记 task_type 值: {unknown}"
