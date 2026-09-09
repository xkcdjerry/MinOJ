"""提交业务逻辑：创建、列表、详情、重评、频率限制。"""
import asyncio
import time
from collections import defaultdict, deque

from app import config, storage
from app.errors import OJException
from app.services import judge, user_service

# user_id -> 最近提交时间戳（秒，monotonic）
_rate: dict = defaultdict(deque)


def clear_rate_limit():
    _rate.clear()


def _check_rate(user_id: str):
    now = time.monotonic()
    dq = _rate[user_id]
    while dq and now - dq[0] > config.SUBMIT_RATE_WINDOW:
        dq.popleft()
    if len(dq) >= config.SUBMIT_RATE_LIMIT:
        raise OJException(429, "submission rate limit exceeded")
    dq.append(now)


def _validate_pagination(page, page_size, require_level1: bool, user_id=None, problem_id=None):
    if page is not None and page_size is None:
        raise OJException(400, "page_size is required when page is provided")
    if page is not None and page < 1:
        raise OJException(400, "invalid page")
    if page_size is not None and page_size < 1:
        raise OJException(400, "invalid page_size")
    if require_level1 and not user_id and not problem_id:
        raise OJException(400, "at least one of user_id or problem_id is required")


def _paginate(items: list, page, page_size) -> list:
    if page is None and page_size is None:
        return items
    if page is None:
        return items[:page_size]
    start = (page - 1) * page_size
    return items[start:start + page_size]


async def create_submission(user_id: str, payload) -> dict:
    _check_rate(user_id)  # 429 优先于 404
    problem = await storage.db.problems.get(payload.problem_id)
    if problem is None:
        raise OJException(404, "problem not found")
    lang = await storage.db.languages.get(payload.language)
    if lang is None:
        raise OJException(404, "language not found")

    sub = {
        "user_id": user_id,
        "problem_id": payload.problem_id,
        "language": payload.language,
        "code": payload.code,
        "status": "pending",
        "score": None,
        "counts": None,
        "compile_info": None,
        "run_info": None,
        "error_info": "",
        "details": None,
        "created_at": time.time(),
    }
    submission_id = await storage.db.submissions.next_int_id()
    sub["submission_id"] = submission_id
    await storage.db.submissions.put(submission_id, sub)

    user = await user_service.get_user(user_id)
    if user is not None:
        user["submit_count"] = user.get("submit_count", 0) + 1
        await storage.db.users.put(user_id, user)

    asyncio.create_task(judge.run_judge(submission_id))
    return {"submission_id": submission_id, "status": "pending"}


async def list_submissions(current_user: dict, user_id, problem_id, status, page, page_size) -> dict:
    _validate_pagination(page, page_size, require_level1=True, user_id=user_id, problem_id=problem_id)

    if current_user.get("role") != "admin":
        if user_id is not None and user_id != current_user["user_id"]:
            raise OJException(403, "permission denied")
        user_id = current_user["user_id"]

    matched = []
    for s in storage.db.submissions.data.values():
        if user_id is not None and s.get("user_id") != user_id:
            continue
        if problem_id is not None and s.get("problem_id") != problem_id:
            continue
        if status is not None and s.get("status") != status:
            continue
        matched.append(s)

    matched.sort(key=lambda s: int(s["submission_id"]) if str(s["submission_id"]).isdigit() else s["submission_id"])
    total = len(matched)
    items = _paginate(matched, page, page_size)

    out = []
    for s in items:
        if s.get("status") in ("error", "pending"):
            out.append({"submission_id": s["submission_id"], "status": s["status"]})
        else:
            out.append({
                "submission_id": s["submission_id"],
                "status": s["status"],
                "score": s.get("score"),
                "counts": s.get("counts"),
            })
    return {"total": total, "submissions": out}


def submission_detail(s: dict) -> dict:
    # 规范要求字段全部出现；在此基础上补充 code/language/problem_id/user_id
    # 便于评测详情页展示代码（规范允许额外 key-value）。
    common = {
        "submission_id": s["submission_id"],
        "problem_id": s.get("problem_id"),
        "user_id": s.get("user_id"),
        "language": s.get("language"),
        "code": s.get("code", ""),
    }
    if s.get("status") == "pending":
        return {
            **common,
            "status": "pending",
            "score": None,
            "counts": None,
            "compile_info": None,
            "run_info": None,
            "error_info": "",
        }
    return {
        **common,
        "status": s["status"],
        "score": s.get("score"),
        "counts": s.get("counts"),
        "compile_info": s.get("compile_info"),
        "run_info": s.get("run_info"),
        "error_info": s.get("error_info", ""),
    }


async def rejudge(submission_id: str) -> dict:
    sub = await storage.db.submissions.get(submission_id)
    if sub is None:
        raise OJException(404, "submission not found")
    sub.update({
        "status": "pending",
        "score": None,
        "counts": None,
        "compile_info": None,
        "run_info": None,
        "error_info": "",
        "details": None,
    })
    await storage.db.submissions.put(submission_id, sub)
    asyncio.create_task(judge.run_judge(submission_id))
    return {"submission_id": submission_id, "status": "pending"}
