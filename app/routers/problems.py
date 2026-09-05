"""题目管理 API（Step 1）。"""
from fastapi import APIRouter, Depends

from app import storage
from app.deps import get_current_user, require_admin
from app.errors import OJException, ok
from app.schemas import ProblemModel
from app.services import problem_service

router = APIRouter()


@router.get("/api/problems/")
async def list_problems(current_user: dict = Depends(get_current_user)):
    problems = sorted(storage.db.problems.data.values(), key=lambda p: p.get("id", ""))
    data = [{"id": p.get("id"), "title": p.get("title", "")} for p in problems]
    return ok("success", data)


@router.post("/api/problems/")
async def add_problem(body: ProblemModel, current_user: dict = Depends(get_current_user)):
    if await storage.db.problems.get(body.id) is not None:
        raise OJException(409, "problem id already exists")
    await storage.db.problems.put(body.id, body.model_dump())
    return ok("add success", {"id": body.id})


@router.get("/api/problems/{problem_id}")
async def get_problem(problem_id: str, current_user: dict = Depends(get_current_user)):
    p = await storage.db.problems.get(problem_id)
    if p is None:
        raise OJException(404, "problem not found")
    return ok("success", problem_service.problem_to_public(p))


@router.put("/api/problems/{problem_id}")
async def edit_problem(problem_id: str, body: ProblemModel, current_user: dict = Depends(get_current_user)):
    if body.id != problem_id:
        raise OJException(400, "problem id mismatch")
    existing = await storage.db.problems.get(problem_id)
    if existing is None:
        raise OJException(404, "problem not found")
    data = body.model_dump()
    # 日志可见性不在题目编辑字段内，编辑时应保留原有设置
    data["public_cases"] = existing.get("public_cases", False)
    await storage.db.problems.put(problem_id, data)
    return ok("update success", {"id": problem_id})


@router.delete("/api/problems/{problem_id}")
async def delete_problem(problem_id: str, current_user: dict = Depends(require_admin)):
    if await storage.db.problems.get(problem_id) is None:
        raise OJException(404, "problem not found")
    await problem_service.delete_problem_cascade(problem_id)
    return ok("delete success", {"id": problem_id})
