"""AI 智能命题：模型配置、任务状态机、实时事件、中断、Token/费用统计。

模型调用走 OpenAI 兼容的 chat/completions；provider_url/model/api_key 均来自
运行时配置，绝不在代码中写死；api_key 不回传、不落日志、不进异常/事件。
"""
import asyncio
import json
import uuid

import httpx
from pydantic import ValidationError

from app import storage
from app.errors import OJException
from app.schemas import ProblemModel

_tasks_registry = {}  # task_id -> asyncio.Task
_events = {}  # task_id -> asyncio.Queue[(event, data)]


def clear_runtime():
    _tasks_registry.clear()
    _events.clear()


def _new_task_id() -> str:
    return "ai-task-" + uuid.uuid4().hex[:8]


def config_public(cfg: dict) -> dict:
    return {
        "provider_url": cfg.get("provider_url", ""),
        "model": cfg.get("model", ""),
        "api_key_configured": bool(cfg.get("api_key")),
        "input_price": cfg.get("input_price", 0.0),
        "output_price": cfg.get("output_price", 0.0),
        "price_unit": cfg.get("price_unit", 1000000),
    }


def task_public(t: dict) -> dict:
    return {
        "task_id": t.get("task_id"),
        "status": t.get("status"),
        "progress": t.get("progress"),
        "result": t.get("result"),
        "usage": t.get("usage"),
    }


def _build_usage(usage: dict, cfg: dict) -> dict:
    """根据模型返回的原始 usage 计算 token 用量与费用。"""
    if not usage:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0, "currency": "USD"}
    it = usage.get("prompt_tokens") or 0
    ot = usage.get("completion_tokens") or 0
    total = usage.get("total_tokens") or (it + ot)
    unit = cfg.get("price_unit") or 1000000
    ip = cfg.get("input_price") or 0.0
    op = cfg.get("output_price") or 0.0
    cost = (it / unit) * ip + (ot / unit) * op
    return {
        "input_tokens": it,
        "output_tokens": ot,
        "total_tokens": total,
        "cost": round(cost, 6),
        "currency": "USD",
    }


def _extract_json(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model did not return valid JSON")
    return json.loads(text[start:end + 1])


def _build_prompt(task: dict) -> str:
    req = task.get("requirement", "")
    ref = f"\n参考题目 id：{task['problem_id']}\n" if task.get("problem_id") else ""
    return (
        "你是 OJ 命题助手。请根据以下命题需求设计一道 OJ 题目，输出一个 JSON 对象，"
        "字段包含：id(字符串,唯一标识)、title、description、input_description、"
        "output_description、samples(数组,元素为{\"input\":\"\",\"output\":\"\"})、"
        "constraints、testcases(数组,元素为{\"input\":\"\",\"output\":\"\"},需覆盖边界条件,至少3个)、"
        "hint、source、tags(字符串数组)、time_limit(数字,秒)、memory_limit(整数,MB)、"
        "author、difficulty。只输出 JSON，不要输出其他文字。\n"
        f"命题需求：{req}\n{ref}"
    )


async def call_model(cfg: dict, task: dict) -> dict:
    """调用 OpenAI 兼容 chat/completions，返回 {"problem": dict, "usage": dict}。

    独立成函数便于测试时 mock。
    """
    url = cfg["provider_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": _build_prompt(task)}],
        "temperature": 0.7,
    }
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise OJException(500, f"model api error: status {resp.status_code}")
    body = resp.json()
    content = body["choices"][0]["message"]["content"]
    problem = _extract_json(content)
    usage = _build_usage(body.get("usage"), cfg)
    return {"problem": problem, "usage": usage}


async def _emit(tid: str, event: str, data):
    q = _events.get(tid)
    if q is None:
        return
    try:
        q.put_nowait((event, data))
    except Exception:
        pass


async def create_task(user_id: str, requirement: str, problem_id=None) -> dict:
    cfg = storage.ai_config.data
    if not (cfg.get("provider_url") and cfg.get("model") and cfg.get("api_key")):
        raise OJException(400, "model config not set")
    if problem_id is not None and await storage.db.problems.get(problem_id) is None:
        raise OJException(404, "problem not found")

    tid = _new_task_id()
    task = {
        "task_id": tid,
        "user_id": user_id,
        "requirement": requirement,
        "problem_id": problem_id,
        "status": "pending",
        "progress": "waiting",
        "result": None,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0.0, "currency": "USD"},
    }
    await storage.db.ai_tasks.put(tid, task)
    _events[tid] = asyncio.Queue()
    t = asyncio.create_task(_run(tid))
    _tasks_registry[tid] = t
    return {"task_id": tid, "status": "pending"}


async def _run(tid: str):
    task = await storage.db.ai_tasks.get(tid)
    if task is None:
        return
    try:
        task["status"] = "running"
        task["progress"] = "正在处理命题需求"
        await storage.db.ai_tasks.put(tid, task)
        await _emit(tid, "progress", {"task_id": tid, "status": "running", "message": "正在处理命题需求"})

        cfg = storage.ai_config.data
        result = await call_model(cfg, task)
        problem_data = result["problem"]
        ProblemModel(**problem_data)  # 校验生成结果，失败抛 ValidationError

        task["result"] = problem_data
        task["usage"] = result["usage"]
        task["status"] = "completed"
        task["progress"] = "命题完成"
        await storage.db.ai_tasks.put(tid, task)
        await _emit(tid, "usage", result["usage"])
        await _emit(tid, "progress", {"task_id": tid, "status": "completed", "message": "命题完成"})
    except asyncio.CancelledError:
        task["status"] = "cancelled"
        task["progress"] = "任务已中断"
        await storage.db.ai_tasks.put(tid, task)
        await _emit(tid, "progress", {"task_id": tid, "status": "cancelled", "message": "任务已中断"})
        raise
    except (ValidationError, Exception) as e:  # noqa: BLE001
        task["status"] = "failed"
        task["progress"] = "命题失败"
        task["result"] = None
        # 错误信息中绝不包含 api_key
        task["error"] = str(e)[:2000]
        await storage.db.ai_tasks.put(tid, task)
        await _emit(tid, "progress", {"task_id": tid, "status": "failed", "message": "命题失败"})
    finally:
        await _emit(tid, "done", {"task_id": tid, "status": task.get("status")})
        _tasks_registry.pop(tid, None)


async def cancel_task(tid: str) -> None:
    t = _tasks_registry.get(tid)
    if t is not None:
        t.cancel()
    else:
        task = await storage.db.ai_tasks.get(tid)
        if task is not None:
            task["status"] = "cancelled"
            task["progress"] = "任务已中断"
            await storage.db.ai_tasks.put(tid, task)


async def iter_events(tid: str, timeout: float = 15.0):
    """SSE 事件生成器（供路由层使用）。"""
    q = _events.get(tid)
    if q is None:
        task = await storage.db.ai_tasks.get(tid)
        yield ("done", {"task_id": tid, "status": task.get("status") if task else "failed"})
        return
    while True:
        try:
            event, data = await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            yield ("keepalive", {})
            continue
        yield (event, data)
        if event == "done":
            break
