"""认证 API（Step 4）：登录 / 登出。"""
from fastapi import APIRouter, Depends, Request

from app.deps import get_current_user
from app.errors import OJException, ok
from app.schemas import LoginModel
from app.services import user_service

router = APIRouter()


@router.post("/api/auth/login")
async def login(request: Request, body: LoginModel):
    user = await user_service.get_user_by_username(body.username)
    if user is None or not user_service.verify_password(body.password, user.get("password_hash", "")):
        raise OJException(401, "invalid username or password")
    if user.get("role") == "banned":
        raise OJException(403, "user is banned")
    request.session["user_id"] = user["user_id"]
    return ok("login success", {
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
    })


@router.post("/api/auth/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    request.session.clear()
    return ok("logout success", None)
