from __future__ import annotations

from datetime import datetime

from nexus.logging import get_logger
from nexus.touch import fingerprint
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.models.reminder import TouchState
from app.services.streak_service import shift_date

logger = get_logger("challengePlanet.touch_gate")

REVIVE_AFTER_DAYS = 7
SUNSET_EPISODE_DAYS = 30


async def _is_unread(notif_id: int) -> bool | None:
    """回执行号→已读状态：True=未读 / False=已读 / None=证据缺失（travelMate 范本语义）。"""
    if not notif_id:
        return None
    try:
        from nexus.notify import get_notify_client

        client = get_notify_client()
        method = getattr(client, "read_status", None)
        if method is None:
            return None
        statuses = await method([int(notif_id)])
    except Exception as e:
        logger.warning("read_status check failed: %s", e)
        return None
    if int(notif_id) not in statuses:
        return None
    return not statuses[int(notif_id)]


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
    fp = fingerprint(kind, int(challenge_id), str(episode_anchor or ""))
    row = await session.get(
        TouchState,
        {"user_id": str(user_id), "challenge_id": int(challenge_id), "kind": kind},
    )
    base = {"fingerprint": fp, "state_row": row}
    if episode_anchor and shift_date(str(episode_anchor), SUNSET_EPISODE_DAYS) <= today:
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
