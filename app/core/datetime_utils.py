from __future__ import annotations

from datetime import datetime
from nexus import TimeUtils


def now_china() -> datetime:
    return TimeUtils.now_naive()
