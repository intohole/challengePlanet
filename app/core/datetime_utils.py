from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

CHINA_TZ = ZoneInfo("Asia/Shanghai")


def now_china() -> datetime:
    return datetime.now(CHINA_TZ).replace(tzinfo=None)
