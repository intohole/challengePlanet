from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from nexus import get_uc_sdk


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 86400
    user: dict[str, object]


@router.get("/config")
async def uc_config() -> dict[str, object]:
    sdk = get_uc_sdk()
    configured = bool(getattr(sdk, "is_configured", lambda: False)())
    app_key = str(getattr(sdk, "app_key", "") or "")
    return {
        "enabled": configured,
        "base_url": "/uc-api" if configured else "",
        "app_key": app_key if configured else "",
    }


@router.post("/register", response_model=LoginResponse)
async def register(req: RegisterRequest) -> LoginResponse:
    try:
        sdk = get_uc_sdk()
    except Exception:
        raise HTTPException(status_code=503, detail="认证服务未配置，请联系管理员")
    try:
        result = await sdk.register(username=req.username, email=req.email or None, password=req.password)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"用户中心暂时不可用: {e}")
    if not result.get("success"):
        detail = result.get("message") or result.get("detail") or "注册失败"
        raise HTTPException(status_code=400, detail=detail)
    data: dict[str, object] = result.get("data", {})
    if not data.get("access_token"):
        raise HTTPException(status_code=400, detail="注册成功但未返回令牌")
    return LoginResponse(
        access_token=str(data["access_token"]),
        refresh_token=str(data.get("refresh_token", "")),
        token_type=str(data.get("token_type", "bearer")),
        expires_in=int(data.get("expires_in", 86400)),
        user=dict(data.get("user", {})),
    )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    try:
        sdk = get_uc_sdk()
    except Exception:
        raise HTTPException(status_code=503, detail="认证服务未配置，请联系管理员")
    try:
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