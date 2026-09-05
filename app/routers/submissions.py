"""评测提交 API（Step 2 & 3）。"""
from typing import Optional

from fastapi import APIRouter, Depends

from app import storage
from app.deps import get_current_user, require_admin
from app.errors import OJException, ok
from app.schemas import SubmissionCreate
from app.services import submission_service

router = APIRouter()


@router.post("/api/submissions/")
async def submit(body: SubmissionCreate, current_user: dict = Depends(get_current_user)):
    data = await submission_service.create_submission(current_user["user_id"], body)
    return ok("success", data)


@router.get("/api/submissions/")
async def list_submissions(
    user_id: Optional[str] = None,
    problem_id: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
):
    data = await submission_service.list_submissions(current_user, user_id, problem_id, status, page, page_size)
    return ok("success", data)


@router.get("/api/submissions/{submission_id}")
async def get_submission(submission_id: str, current_user: dict = Depends(get_current_user)):
    sub = await storage.db.submissions.get(submission_id)
    if sub is None:
        raise OJException(404, "submission not found")
    if current_user.get("role") != "admin" and sub.get("user_id") != current_user["user_id"]:
        raise OJException(403, "permission denied")
    return ok("success", submission_service.submission_detail(sub))


@router.put("/api/submissions/{submission_id}/rejudge")
async def rejudge(submission_id: str, current_user: dict = Depends(require_admin)):
    data = await submission_service.rejudge(submission_id)
    return ok("rejudge started", data)
