"""FastAPI 依赖：当前用户 / 管理员校验。

权限判断顺序：401（未登录）> 403（禁用或无权限）。
"""
from fastapi import Depends, Request

from app.errors import OJException
from app.services import user_service


async def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise OJException(401, "not logged in")
    user = await user_service.get_user(user_id)
    if user is None:
        raise OJException(401, "not logged in")
    if user.get("role") == "banned":
        raise OJException(403, "user is banned")
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise OJException(403, "permission denied")
    return current_user
