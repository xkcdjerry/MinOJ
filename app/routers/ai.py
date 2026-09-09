"""AI 智能命题 API（Advance：R1–R4）。"""
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app import storage
from app.deps import get_current_user
from app.errors import OJException, ok
from app.schemas import AIConfigModel, AITaskCreate
from app.services import ai_service

router = APIRouter()


@router.put("/api/ai/model-config")
async def set_model_config(body: AIConfigModel, current_user: dict = Depends(get_current_user)):
    cfg = body.model_dump()
    await storage.db.ai_config.set(cfg)
    return ok("model config updated", ai_service.config_public(cfg))


@router.get("/api/ai/model-config")
async def get_model_config(current_user: dict = Depends(get_current_user)):
    return ok("success", ai_service.config_public(storage.db.ai_config.data))


@router.post("/api/ai/problem-tasks/")
async def create_problem_task(body: AITaskCreate, current_user: dict = Depends(get_current_user)):
    data = await ai_service.create_task(current_user["user_id"], body.requirement, body.problem_id, body.inplace)
    return ok("task created", data)


@router.get("/api/ai/problem-tasks/{task_id}")
async def get_problem_task(task_id: str, current_user: dict = Depends(get_current_user)):
    t = await storage.db.ai_tasks.get(task_id)
    if t is None:
        raise OJException(404, "task not found")
    if current_user.get("role") != "admin" and t.get("user_id") != current_user["user_id"]:
        raise OJException(403, "permission denied")
    return ok("success", ai_service.task_public(t))


@router.put("/api/ai/problem-tasks/{task_id}/cancel")
async def cancel_problem_task(task_id: str, current_user: dict = Depends(get_current_user)):
    t = await storage.db.ai_tasks.get(task_id)
    if t is None:
        raise OJException(404, "task not found")
    if current_user.get("role") != "admin" and t.get("user_id") != current_user["user_id"]:
        raise OJException(403, "permission denied")
    if t.get("status") in ("completed", "cancelled", "failed"):
        raise OJException(409, "task already ended")
    await ai_service.cancel_task(task_id)
    return ok("task cancelled", {"task_id": task_id, "status": "cancelled"})


@router.get("/api/ai/problem-tasks/{task_id}/events")
async def problem_task_events(task_id: str, current_user: dict = Depends(get_current_user)):
    t = await storage.db.ai_tasks.get(task_id)
    if t is None:
        raise OJException(404, "task not found")
    if current_user.get("role") != "admin" and t.get("user_id") != current_user["user_id"]:
        raise OJException(403, "permission denied")

    async def gen():
        async for event, data in ai_service.iter_events(task_id):
            if event == "keepalive":
                yield ": keep-alive\n\n"
                continue
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
