from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    uc_url = settings.UC_BASE_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{uc_url}/api/auth/login",
            json={
                "username": req.username,
                "password": req.password,
                "app_key": settings.UC_APP_KEY,
            },
        )
    data = resp.json()
    if not data.get("success"):
        detail = data.get("message") or data.get("detail") or "登录失败"
        raise HTTPException(status_code=401, detail=detail)
    token_data = data.get("data", {})
    if not token_data.get("access_token"):
        raise HTTPException(status_code=401, detail="用户中心未返回有效令牌")
    return LoginResponse(
        access_token=token_data["access_token"],
        token_type=token_data.get("token_type", "bearer"),
        expires_in=token_data.get("expires_in", 86400),
        user=token_data.get("user", {}),
    )
