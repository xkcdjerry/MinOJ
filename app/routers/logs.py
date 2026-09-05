"""评测日志与访问审计 API（Step 5）。"""
from typing import Optional

from fastapi import APIRouter, Depends

from app import config, storage
from app.deps import get_current_user, require_admin
from app.errors import OJException, ok
from app.schemas import LogVisibilityModel
from app.services import user_service

router = APIRouter()


@router.get("/api/submissions/{submission_id}/log")
async def get_log(submission_id: str, current_user: dict = Depends(get_current_user)):
    sub = await storage.db.submissions.get(submission_id)
    if sub is None:
        raise OJException(404, "submission not found")

    problem = await storage.db.problems.get(sub.get("problem_id"))
    public = bool(problem and problem.get("public_cases"))
    is_owner = sub.get("user_id") == current_user["user_id"]
    is_admin = current_user.get("role") == "admin"

    if not (is_owner or is_admin or public):
        await storage.access_log.append({
            "user_id": current_user["user_id"],
            "problem_id": sub.get("problem_id"),
            "action": config.ACCESS_LOG_ACTION,
            "time": user_service.now_date(),
            "status": "403",
        })
        raise OJException(403, "permission denied")

    await storage.access_log.append({
        "user_id": current_user["user_id"],
        "problem_id": sub.get("problem_id"),
        "action": config.ACCESS_LOG_ACTION,
        "time": user_service.now_date(),
        "status": "200",
    })
    return ok("success", {
        "details": sub.get("details"),
        "score": sub.get("score"),
        "counts": sub.get("counts"),
    })


@router.put("/api/problems/{problem_id}/log_visibility")
async def set_log_visibility(
    problem_id: str, body: LogVisibilityModel, current_user: dict = Depends(require_admin)
):
    p = await storage.db.problems.get(problem_id)
    if p is None:
        raise OJException(404, "problem not found")
    p["public_cases"] = body.public_cases if body.public_cases is not None else False
    await storage.db.problems.put(problem_id, p)
    return ok("log visibility updated", {"problem_id": problem_id, "public_cases": p["public_cases"]})


@router.get("/api/logs/access/")
async def list_access_logs(
    user_id: Optional[str] = None,
    problem_id: Optional[str] = None,
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

    filtered = []
    for e in storage.access_log.entries:
        if user_id is not None and e.get("user_id") != user_id:
            continue
        if problem_id is not None and e.get("problem_id") != problem_id:
            continue
        filtered.append(e)
    filtered = list(reversed(filtered))  # 最近的在前

    if page is None and page_size is None:
        items = filtered
    elif page is None:
        items = filtered[:page_size]
    else:
        start = (page - 1) * page_size
        items = filtered[start:start + page_size]
    return ok("success", items)
