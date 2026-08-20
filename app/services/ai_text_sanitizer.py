from __future__ import annotations

import re

_PROMPT_MARKERS: tuple[str, ...] = (
    "语言规范",
    "反馈结构",
    "方向语义",
    "开头示例",
    "语言策略",
    "觉察肯定",
    "模式观察",
    "微行动建议",
    "输出只呈现",
    "对用户说的话本身",
    "输出严格JSON",
    "只输出严格",
    "不要输出任何",
    "不要markdown",
    "不允许输出",
    "严禁",
    "禁用评判词",
    "改用理解词",
    "严格遵守",
    "据此重新生成",
    "系统提示",
    "系统prompt",
    "system prompt",
    "忽略上面",
    "忽略以上",
    "以上是系统",
    "以下是系统",
    "不要复述",
)

_HEADING_RE = re.compile(r"^\s*(?:系统提示(?:词)?|system\b|prompt\b|以下是|以上是)[：:\-\s]*", re.IGNORECASE)

_BLOCK_BRACKET_RE = re.compile(r"【[^】]{0,16}(?:规范|结构|策略|语义|场景|要求|规则|指令)】")

_ROLE_ECHO_RE = re.compile(
    r"^(?:你是一(?:个|位)|你是)\S{0,14}(?:伙伴|教练|助手|解析器|分析师|专家|导师|高手)"
)


def sanitize_coach_text(raw: str, fallback: str = "", max_len: int = 200) -> str:
    text = (raw or "").strip()
    if not text:
        return fallback
    lines = [ln.strip() for ln in text.splitlines()]
    clean: list[str] = []
    for ln in lines:
        if not ln:
            clean.append("")
            continue
        if _is_prompt_marker(ln, ln.lower()):
            continue
        clean.append(ln)
    text = "\n".join(clean).strip()
    text = _strip_code_fence(text)
    text = _strip_leading_heading(text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return fallback
    if _is_prompt_marker(text, text.lower()):
        return fallback
    text = text[:max_len].strip()
    return text


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


def _strip_code_fence(text: str) -> str:
    return re.sub(r"^```[a-z]*\s*|\s*```$", "", text).strip()


def _strip_leading_heading(text: str) -> str:
    return _HEADING_RE.sub("", text, count=1).strip()