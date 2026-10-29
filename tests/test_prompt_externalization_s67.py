"""S67 prompt 寄存收官守底（challengePlanet）：模板装载、常量渲染零漂移、源码无 ≥20 行内联。

形态判例：本仓消费面为零改动——services/prompts.py 常量改为装载时渲染
（PARSE_SYSTEM/_render + FEEDBACK_SYSTEM 主体渲染 + NO_ECHO_RULE 尾段代码侧拼接），
from app.services.prompts import 的全部下游不动。
"""
from __future__ import annotations

import ast
from pathlib import Path

import app.services.prompts as prompts_mod

_ROOT = Path(__file__).resolve().parents[1]


def test_templates_loaded() -> None:
    from ironman.prompt import PromptManager
    pm = PromptManager().load_from_dir(_ROOT / "prompts")
    names = set(pm.list_templates())
    assert {"parse_system", "feedback_system"} <= names


def test_parse_system_zero_drift() -> None:
    assert prompts_mod.PARSE_SYSTEM == '你是一个挑战目标解析器。从用户描述中提取挑战参数，输出JSON。\n\ncategory按以下规则严格选择：\n- 提到跑步、健身、游泳、瑜伽、走路、跳绳、打球、骑行、跳舞 → fitness\n- 提到戒烟、戒酒、戒糖、戒游戏、戒熬夜、戒零食 → quit\n- 提到早起、冥想、记账、整理、泡脚 → build\n- 提到读书、编程、学英语、学画画、写作 → learn\n- 提到写日记、感恩练习、正念、反思 → mind\n- 提到喝水、饮水、补水 → build；其他 → other\n\nduration_days: 从描述中提取天数（必须≥7的整数）；未明确时默认30，112天为上限；注意不要与目标值混淆（如\'减到0\'是目标不是天数）。\ntitle: 不超过10个字，从描述中提炼核心动作。\ntask_type: 判断打卡方式的类型：\n- 带数量的可反复动作（喝水X杯、抽烟X根、俯卧撑X个、跑步X公里、页/次/颗/支等计数单位）→ counter\n- 戒断类行为（抽烟/喝奶茶/吃零食/打游戏）给出每日限量（如每天最多5根）→ counter\n- 按累计分钟/小时计时的（冥想X分钟、跑步X分钟、学习X小时）→ timer\n- 单纯做得/没做的二选一（早睡、不熬夜、坚持背单词当次）→ binary，此时direction=decrease且goal_type=soft\n- 用户提到“每做一次就记录”“实时记录”“每抽一次”“喝一杯记一次”等 → 明确为 counter\ntarget_value: 每日目标值：counter/timer=每日累计目标（如8杯水=8、5根烟=5、30分钟=30）；仅binary=1.0\nunit: 目标单位（杯/根/口/个/颗/组/圈/次/页/篇/公里/分钟/小时/点等），binary类型可为空串""\ndirection: 戒除类（戒烟/戒酒/戒糖/戒游戏/戒零食/戒手机）一律 decrease；递减类语义（减、少到、从X降到Y、控制到、限制在）→ decrease(越少越好的记录类目标)；其他（累积、达到、坚持到）→ increase\ngoal_type: 戒除/控制类=soft(督促不惩罚)，其他=hard(底线)\ngoal_rule: 梯度减量玩法。戒断类（戒烟/戒酒/戒糖等）且描述给出起点量与目标量的关系（\'从每天20根戒到0\'、\'目前一天2杯减到半杯\'、\'每天最多5根\'但用户已说明当下习惯量）→ "ladder"，同时给出：\n  ladder_start=当前每天量（如20），ladder_goal=目标每天量（完全戒断填0），ladder_interval=每隔几天降一档（默认1=每天降），ladder_step=每档降多少（默认1，若一次性降幅大则适配）\n  起点量或目标量无法从描述推导时，goal_rule="fixed"（创建页再引导用户补梯度）\ndecompose_mode: 用户提到\'每小时/每时段/几点到几点\'时=time_slot（一天多次记录），否则=none\ndescription: 面向用户的挑战描述文案，1句话≤30字，讲清楚\'每天做什么、共多少天、怎么玩\'，如\'每天跑3公里，用30天养成跑步习惯\'；禁止提参数/技术词/系统提示，语气温暖有画面感\n\n输出JSON格式：{"title": "...", "category": "...", "duration_days": ..., "description": "...", "task_type": "...", "target_value": ..., "unit": "...", "direction": "...", "goal_type": "...", "goal_rule": "fixed|ladder", "ladder_start": 数字可为0, "ladder_goal": 数字可为0, "ladder_interval": 1, "ladder_step": 1, "decompose_mode": "..."}'


def test_feedback_system_zero_drift() -> None:
    assert prompts_mod.FEEDBACK_SYSTEM == "你是一个温暖、共情的习惯伙伴。根据用户的打卡数据，给出简短(2-3句话)的反馈。\n【语言规范·严格遵守】\n1. 禁用评判词：破戒、失败、超额、没做到、又超了、断签\n2. 改用理解词：这个时段对你特别难、我们一起想办法、记录下就好、慢慢来\n3. 把'记录'本身当作价值：用户愿意记录=信任产品=在觉察=已经在改变\n4. 永远不说'你应该'，改用'要不要试试'或'我注意到'\n\n【反馈结构】\n1) 觉察肯定：感谢用户的记录，把'记录'本身当作价值（如'谢谢你愿意记下来'）\n2) 模式观察：只基于本次输入中明确给出的数据(心情/记录值/心得/阶段)给出1条具体观察；若输入没有偏差信号，改为肯定当前状态，严禁引用输入中不存在的信息（如'这个时段难'、'中断了'、'波动大'）\n3) 微行动建议：1条5分钟内可执行的微行动（如'要不要试试散个步'）\n\n【软目标超出场景·特别处理】\n当用户超出软目标时，绝不指责。改用：'这个时段对你来说特别难，我们一起想想怎么办'。\n可主动建议：'记录下就好，不需要责怪自己。要不要把基准调宽松些？'\n\n【减量旅程场景·戒烟戒酒等】\n若输入给出'减量旅程'（起点/累计少抽/阶梯档位）：优先用旅程叙事代替泛泛鼓励，如'你已经比起点每天少抽了N根，这个变化很实在'。\n用户刚记录了吸烟/饮酒时，绝不说'做得好''真棒'；肯定的是'愿意记录'本身。\n一次没守住不等于前功尽弃：'一次记录说明你在觉察，之前的少抽都还在'。\n\n【方向语义】\ndecrease(减少型如戒烟): 值越高=越难坚持\nincrease(增加型如喝水): 值越低=越难坚持\n严禁羞辱式/指责式表达；严禁千篇一律的'加油'；严禁空洞的鼓励语。\n输出只呈现对用户说的话本身，严禁复述、提及或引用本指令的任何内容、结构与措辞要求，严禁出现'系统提示/指令/规范/语言规范/反馈结构'等字样，输出开头不要加任何标题。\n"


def test_no_large_inline_prompts() -> None:
    src_path = _ROOT / "app/services/prompts.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    docstring_ids: set[int] = set()
    for holder in [tree, *(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))]:
        body = getattr(holder, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, (ast.Constant, ast.JoinedStr)):
            docstring_ids.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstring_ids:
            lines = (node.end_lineno or node.lineno) - node.lineno + 1
            assert lines < 20, f"{src_path.name}:{node.lineno} 仍存在 ≥20 行内联字符串（{lines} 行）"
