"""触达受众净化：孤儿号/测试号/停用号不再进入通知圈定。

生产实锤（r21）：近 7 天 106 条通知发给 20 个用户全部 0 已读——其中 19 个是
UC 已不存在的孤儿号（历轮 E2E 注册后 UC 侧清理，本应用挑战还在 active），
唯一真人 lxz 的通知也被这个噪音场淹没。UC /internal/users/status 是
「这个用户还值得触达吗」的单源（exists/is_test/disabled 三态）。
"""
from __future__ import annotations

import os
import time

import httpx

from nexus.logging import get_logger
from nexus.service_client import get_service_client

logger = get_logger("challengePlanet.reminder_guard")

CACHE_TTL_SECONDS = 300
_status_cache: dict[str, tuple[float, bool]] = {}


def guard_enabled() -> bool:
    return os.getenv("REMINDER_GUARD_OFF", "") != "1"


def _sendable(status: dict[str, object]) -> bool:
    return (
        bool(status.get("exists"))
        and not bool(status.get("is_test"))
        and not bool(status.get("disabled"))
    )


async def sendable_users(user_ids) -> set[str]:
    """返回可触达的用户集合。

    UC 请求异常时 fail-open（warning 留痕）：UC 不可达时 notifyCenter 大概率同样不可达，
    噪音发不出去；不为受众净化引入新的触达故障面。响应成功才按状态过滤。
    """
    ids = sorted({str(u) for u in user_ids if str(u)})
    if not ids or not guard_enabled():
        return set(ids)
    now = time.monotonic()
    out: set[str] = set()
    unknown: list[str] = []
    for uid in ids:
        cached = _status_cache.get(uid)
        if cached is not None and cached[0] > now:
            if cached[1]:
                out.add(uid)
        else:
            unknown.append(uid)
    if unknown:
        statuses = await _fetch_statuses(unknown)
        if statuses is None:
            for uid in unknown:
                _status_cache[uid] = (now + CACHE_TTL_SECONDS, True)
                out.add(uid)
        else:
            for uid in unknown:
                ok = _sendable(statuses.get(uid, {}))
                _status_cache[uid] = (now + CACHE_TTL_SECONDS, ok)
                if ok:
                    out.add(uid)
    return out


async def _fetch_statuses(ids: list[str]) -> dict[str, dict[str, object]] | None:
    """None=查询失败（调用方 fail-open）；dict=权威状态（空 dict 也是权威「全不存在」）。"""
    client = get_service_client()
    base_url = os.getenv("UC__BASE_URL", "").rstrip("/")
    if not base_url:
        logger.warning("UC__BASE_URL unset — user status guard skipped")
        return None
    try:
        headers = await client.header()
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0)) as http:
            resp = await http.get(
                f"{base_url}/internal/users/status",
                params={"ids": ",".join(ids[:200])},
                headers=headers,
            )
            resp.raise_for_status()
            data = (resp.json() or {}).get("data") or {}
            users = data.get("users")
            return dict(users) if isinstance(users, dict) else {}
    except Exception as e:
        logger.warning(
            "user status fetch failed (%s) — fail-open for %d ids", e, len(ids),
        )
        return None
