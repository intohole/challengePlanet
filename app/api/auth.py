from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from nexus import get_uc_sdk

from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 86400
    user: dict[str, object]


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    if not settings.UC_BASE_URL or not settings.UC_APP_KEY:
        raise HTTPException(status_code=503, detail="认证服务未配置，请联系管理员")
    try:
        sdk = get_uc_sdk()
        result = await sdk.login(username=req.username, password=req.password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"用户中心暂时不可用: {e}")
    if not result.get("success"):
        detail = result.get("message") or result.get("detail") or "登录失败"
        raise HTTPException(status_code=401, detail=detail)
    data: dict[str, object] = result.get("data", {})
    if not data.get("access_token"):
        raise HTTPException(status_code=401, detail="用户中心未返回有效令牌")
    return LoginResponse(
        access_token=str(data["access_token"]),
        refresh_token=str(data.get("refresh_token", "")),
        token_type=str(data.get("token_type", "bearer")),
        expires_in=int(data.get("expires_in", 86400)),
        user=dict(data.get("user", {})),
    )