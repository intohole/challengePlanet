from __future__ import annotations

from datetime import datetime

from nexus.logging import get_logger
from nexus.notify import unread_status as _is_unread  # noqa: F401 — travelMate 范本收归 r160，测试 patch 面沿本模块属性
from nexus.touch import fingerprint
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.models.reminder import TouchState
from app.services.streak_service import shift_date

logger = get_logger("challengePlanet.touch_gate")

REVIVE_AFTER_DAYS = 7
SUNSET_EPISODE_DAYS = 30

_LAST_GATE_LOG: dict[tuple[str, int, str], str] = {}


def episode_over(episode_anchor: str, today: str) -> bool:
    """episode 是否已越过 SUNSET 线（r26 起触达 gate 与呈现面 resting 迁移共用本判定）。

    语义：同一次失踪（episode_anchor=最后一次在场日）超过 SUNSET_EPISODE_DAYS
    即告一段落——gate 停止触达，呈现面迁入 resting，复活后新 episode 自动解除。
    """
    if not episode_anchor:
        return False
    return shift_date(str(episode_anchor), SUNSET_EPISODE_DAYS) <= str(today)


def effective_anchor(episode_anchor: str, episode_floor: str) -> str:
    """episode 锚下限（r26）：复活重开的新 episode 从 start_date 起算缺席钟。

    历史 last_seen 早于新起点时（resting→revive 重置了 start_date，旧打卡保留），
    锚抬到起点——否则复活挑战会在下一次 gate/列表瞬间被旧锚判 SUNSET 打回。
    ISO 日期字符串字典序=时间序，max 安全。
    """
    anchor = str(episode_anchor or "")
    floor = str(episode_floor or "")
    if not anchor:
        return floor
    if not floor:
        return anchor
    return max(anchor, floor)


def log_gate_decision(
    kind: str, challenge_id: int, action: str, reason: str, extra: str = "",
) -> None:
    """gate 决策日志按 (kind, challenge, action) 去重：同决策首次 INFO、重复降 DEBUG。

    节拍任务每小时跑，sunset/silence 的重复决策曾每天刷 200+ 行同文日志
    （4 个死挑战 × 24 小时 × 双引擎）；首现 INFO 保留可观测，重复 DEBUG 保信噪比。
    """
    key = (str(kind), int(challenge_id), str(action))
    line = (
        f"touch gate {kind}: challenge {challenge_id} action={action} ({reason})"
        + (f" {extra}" if extra else "")
    )
    if _LAST_GATE_LOG.get(key) == str(reason):
        logger.debug(line)
        return
    _LAST_GATE_LOG[key] = str(reason)
    logger.info(line)


async def decide_touch_kind(
    session: AsyncSession,
    *,
    kind: str,
    challenge_id: int,
    user_id: str,
    episode_anchor: str,
    today: str,
    now: datetime | None = None,
    legacy_sent_at: datetime | None = None,
    legacy_notif_id: int = 0,
    episode_floor: str = "",
) -> dict[str, object]:
    """触达语义决策层（缺席陪伴的 REVIVE/SUNSET 语义；频率控制留在各引擎节奏层）。

    两个钟：
    - 缺席钟锚 episode 起点（最后一次记录日）——同一次失踪超 30 天 SUNSET 诚实退场，
      回流后新 episode 指纹自然变化即自动解除；
    - 发送钟锚上次触达——同 episode 距上次 ≥7 天 REVIVE「门开着」变体，否则 SILENCE。
    lane：REVIVE 查上次通知未读回执——未读=door（门开着文案）/已读未行动=switch（换道文案，
    给安静出口）/证据缺失=door（不把证据缺失当已读）。
    legacy_sent_at：TouchState 上线前的存量 insight 回退（同 episode 已 care 过的旧账），
    防止新表无历史导致同 episode 重发首触。
    返回 {action: send|revive|silence|sunset, reason, lane, fingerprint, state_row}。
    """
    now = now or now_china()
    anchor = effective_anchor(episode_anchor, episode_floor)
    fp = fingerprint(kind, int(challenge_id), str(anchor))
    row = await session.get(
        TouchState,
        {"user_id": str(user_id), "challenge_id": int(challenge_id), "kind": kind},
    )
    base = {"fingerprint": fp, "state_row": row}
    if episode_over(anchor, today):
        return {
            **base, "action": "sunset", "lane": "sunset",
            "reason": f"episode_over_{SUNSET_EPISODE_DAYS}d",
        }
    same_episode_row = row if (row is not None and row.fingerprint == fp) else None
    if same_episode_row is not None:
        last_sent = same_episode_row.last_sent_at
        notif_id = int(same_episode_row.last_notif_id or 0)
    elif legacy_sent_at is not None:
        last_sent, notif_id = legacy_sent_at, int(legacy_notif_id)
    else:
        return {**base, "action": "send", "lane": "default", "reason": "first_touch_in_episode"}
    if last_sent is None:
        return {**base, "action": "send", "lane": "default", "reason": "no_send_clock"}
    if (now - last_sent).days >= REVIVE_AFTER_DAYS:
        unread = await _is_unread(notif_id) if notif_id else None
        lane = "door" if unread is not False else "switch"
        return {**base, "action": "revive", "lane": lane, "reason": "same_episode_revive"}
    return {**base, "action": "silence", "lane": "default", "reason": "same_episode_recent"}


async def mark_touch_sent(
    session: AsyncSession,
    *,
    user_id: str,
    challenge_id: int,
    kind: str,
    fingerprint_value: str,
    notif_id: int,
    action: str,
) -> None:
    """发送确认后落触达状态（先发送后落痕纪律的状态机版）。"""
    row = await session.get(
        TouchState,
        {"user_id": str(user_id), "challenge_id": int(challenge_id), "kind": kind},
    )
    if row is None:
        row = TouchState(user_id=str(user_id), challenge_id=int(challenge_id), kind=kind)
        session.add(row)
    row.fingerprint = str(fingerprint_value)
    row.last_sent_at = now_china()
    row.last_notif_id = int(notif_id or 0)
    row.last_action = str(action)
    await session.flush()
