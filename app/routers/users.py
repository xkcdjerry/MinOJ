"""用户管理 API（Step 4）。"""
from typing import Optional

from fastapi import APIRouter, Depends

from app import storage
from app.deps import get_current_user, require_admin
from app.errors import OJException, ok
from app.schemas import RegisterModel, RoleModel
from app.services import user_service

router = APIRouter()


@router.post("/api/users/")
async def register(body: RegisterModel):
    user_service.validate_username_password(body.username, body.password)
    user = await user_service.create_user(body.username, body.password, role="user")
    return ok("register success", user_service.public_user(user))


@router.post("/api/users/admin")
async def create_admin(body: RegisterModel, current_user: dict = Depends(require_admin)):
    user_service.validate_username_password(body.username, body.password)
    user = await user_service.create_user(body.username, body.password, role="admin")
    return ok("success", {"user_id": user["user_id"], "username": user["username"]})


@router.get("/api/users/")
async def list_users(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    current_user: dict = Depends(require_admin),
):
    if page is not None and page_size is None:
        raise OJException(400, "page_size is required when page is provided")
    if page is not None and page < 1:
        raise OJException(400, "invalid page")
    if page_size is not None and page_size < 1:
        raise OJException(400, "invalid page_size")

    users = await user_service.list_users()
    total = len(users)
    if page is None and page_size is None:
        items = users
    elif page is None:
        items = users[:page_size]
    else:
        start = (page - 1) * page_size
        items = users[start:start + page_size]
    return ok("success", {"total": total, "users": items})


@router.get("/api/users/{user_id}")
async def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    user = await user_service.get_user(user_id)
    if user is None:
        raise OJException(404, "user not found")
    if current_user.get("role") != "admin" and current_user["user_id"] != user_id:
        raise OJException(403, "permission denied")
    return ok("success", user_service.public_user(user))


@router.put("/api/users/{user_id}/role")
async def update_role(user_id: str, body: RoleModel, current_user: dict = Depends(require_admin)):
    if body.role not in ("admin", "user", "banned"):
        raise OJException(400, "invalid role")
    user = await user_service.get_user(user_id)
    if user is None:
        raise OJException(404, "user not found")
    user["role"] = body.role
    await storage.db.users.put(user_id, user)
    return ok("role updated", {"user_id": user_id, "role": body.role})
