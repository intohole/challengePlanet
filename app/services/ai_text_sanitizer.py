from __future__ import annotations

import re

_PROMPT_MARKERS: tuple[str, ...] = (
    "语言规范", "反馈结构", "方向语义", "开头示例", "语言策略",
    "觉察肯定", "模式观察", "微行动建议", "输出只呈现", "对用户说的话本身",
    "输出严格JSON", "只输出严格", "不要输出任何", "不要markdown", "不允许输出",
    "严禁", "禁用评判词", "改用理解词", "严格遵守", "据此重新生成",
    "系统提示", "系统prompt", "system prompt", "忽略上面", "忽略以上",
    "以上是系统", "以下是系统", "不要复述", "下面提供的指令", "根据用户的打卡数据",
    "给出简短", "记录'本身当作价值", "输入会给出风险信号", "一并", "据此再来",
    "现在我给你", "请只输出", "按照上面", "如上面", "按以下",
)

_USER_LABELS: tuple[str, ...] = (
    "挑战：", "心情：", "心得：", "本次记录值：", "目标值：",
    "方向：", "最近打卡", "用户过往记忆", "断签风险信号",
)

_HEADING_RE = re.compile(
    r"^\s*(?:系统提示(?:词)?|system\b|prompt\b|以下是|以上是|作为[^。]{0,8}输出目标)[：:\-\s]*",
    re.IGNORECASE,
)

_BLOCK_BRACKET_RE = re.compile(r"【[^】]{0,24}(?:语言|反馈|方向|系统|策略|结构|规范|语义|场景|要求|规则|指令|特别|当前)】")

_ROLE_ECHO_RE = re.compile(
    r"^(?:你是一(?:个|位)|你是|你将担任)\S{0,16}(?:伙伴|教练|助手|解析器|分析师|专家|导师|高手|解析员)"
)

_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_coach_text(
    raw: str, system: str = "", fallback: str = "", max_len: int = 220,
) -> str:
    text = (raw or "").strip()
    if not text:
        return fallback
    sys_lines = _system_lines(system)
    clean: list[str] = []
    for ln in (line.strip() for line in text.splitlines()):
        if not ln:
            if clean and clean[-1] != "":
                clean.append("")
            continue
        if sys_lines and _normalize(ln) in sys_lines:
            continue
        if _is_prompt_marker(ln, ln.lower()):
            continue
        clean.append(ln)
    text = _collapse_blank("\n".join(clean).strip())
    text = _strip_code_fence(text)
    text = _strip_leading_heading(text)
    text = _collapse_blank(text)
    if not text:
        return fallback
    picked = _kernel(text)
    if _is_leak(text, picked):
        return fallback
    if len(text) >= 4 and _is_prompt_marker(text, text.lower()):
        return fallback
    text = text[:max_len].strip()
    text = _collapse_blank(text)
    return text if text else fallback


def _is_prompt_marker(line: str, lowered: str) -> bool:
    if _HEADING_RE.search(lowered):
        return True
    if _BLOCK_BRACKET_RE.search(line):
        return True
    if _ROLE_ECHO_RE.search(line):
        return True
    for marker in _PROMPT_MARKERS:
        if marker in line:
            return True
    return False


def _system_lines(system: str) -> set[str]:
    if not system:
        return set()
    out: set[str] = set()
    for seg in system.splitlines():
        seg = seg.strip()
        if not seg:
            continue
        out.add(_normalize(seg))
    return out


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub("", text).strip("，。！？、；：\"'「」『』\n\t ")


def _collapse_blank(text: str) -> str:
    return re.sub(r"\n{2,}", "\n\n", text).strip()


def _strip_code_fence(text: str) -> str:
    return re.sub(r"^```[a-z]*\s*|\s*```$", "", text).strip()


def _strip_leading_heading(text: str) -> str:
    return _HEADING_RE.sub("", text, count=1).strip()


def _kernel(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[:8]


def _is_leak(text: str, picked: list[str]) -> bool:
    if len(picked) <= 1:
        return False
    label_hits = sum(1 for label in _USER_LABELS if label in text)
    if label_hits >= 2:
        return True
    no_space = _WHITESPACE_RE.sub("", text)
    if len(no_space) > 60:
        instruction = 0
        for line in picked:
            if _is_prompt_marker(line, line.lower()):
                instruction += 1
        if instruction >= max(2, len(picked) // 2):
            return True
    return False