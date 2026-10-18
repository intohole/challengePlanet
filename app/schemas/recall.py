from __future__ import annotations

from pydantic import BaseModel


class RecallTrackRequest(BaseModel):
    challenge_id: int = 0
    channel: str = ""
    stage: str = ""
    notif_id: str = ""
    detail: str = ""
