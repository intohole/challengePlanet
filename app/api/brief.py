from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.brief_service import build_brief_snapshot

router = APIRouter()


@router.get("/snapshot")
async def brief_snapshot(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """灵犀晨报/今日面专用只读快照：挑战动静+回归语境+重启卡在场。

    纯只读（#1051）：不创建建议、不推进状态、不迁移 resting；写链由
    tests/test_brief_snapshot_r28.py 哨兵钉死。委外消费方每日委托调用本端点
    不会放大任何写入。
    """
    return await build_brief_snapshot(session, user_id)
