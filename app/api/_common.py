from __future__ import annotations

from fastapi import HTTPException


def bad_request(e: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))
