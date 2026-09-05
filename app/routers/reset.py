"""系统重置 API（测试支持）。"""
from fastapi import APIRouter, Depends, Request

from app.deps import require_admin
from app.errors import ok
from app.services import reset_service

router = APIRouter()


@router.post("/api/reset/")
async def reset(request: Request, current_user: dict = Depends(require_admin)):
    request.session.clear()
    await reset_service.reset_all()
    return ok("system reset successfully", None)
