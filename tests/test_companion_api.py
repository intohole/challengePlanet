"""companion-status 接口测试 — 验证轻量状态接口返回 meta。"""

from __future__ import annotations

import pytest

from app.api.challenge import get_companion_status


@pytest.mark.asyncio
async def test_companion_status_ok(monkeypatch) -> None:
    async def fake_load(user_id: str, challenge_id: int) -> dict:
        return {
            "challenge": object(),
            "checkins": [],
            "completed_days": 3,
            "streak": 2,
            "phase": "adaptation",
            "risk": {"level": "medium", "score": 55},
            "day_number": 5,
            "ladder_progress_pct": 60,
        }

    monkeypatch.setattr("app.api.challenge.load_challenge_state", fake_load)
    result = await get_companion_status(1, user_id="u1")
    assert result["challenge_id"] == 1
    assert result["completed_days"] == 3
    assert result["streak"] == 2
    assert result["risk_level"] == "medium"
    assert result["ladder_progress_pct"] == 60


@pytest.mark.asyncio
async def test_companion_status_not_found(monkeypatch) -> None:
    from fastapi import HTTPException

    async def fake_load(user_id: str, challenge_id: int) -> dict:
        return {"error": "not_found"}

    monkeypatch.setattr("app.api.challenge.load_challenge_state", fake_load)
    with pytest.raises(HTTPException) as exc:
        await get_companion_status(999, user_id="u1")
    assert exc.value.status_code == 404
