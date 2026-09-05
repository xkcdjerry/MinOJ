"""Advance AI 智能命题测试（模型调用被 mock）。"""
import asyncio

from conftest import login
from app.services import ai_service

CFG = {
    "provider_url": "https://model-provider.example/v1",
    "model": "example-model",
    "api_key": "secret-123",
    "input_price": 1.0,
    "output_price": 2.0,
    "price_unit": 1000,
}


def _problem():
    return {
        "id": "ai_1",
        "title": "AI 题",
        "description": "d",
        "input_description": "i",
        "output_description": "o",
        "samples": [{"input": "1", "output": "2"}],
        "constraints": "n<=10",
        "testcases": [{"input": "1", "output": "2"}, {"input": "2", "output": "3"}],
        "hint": "",
        "source": "",
        "tags": [],
        "time_limit": 1.0,
        "memory_limit": 128,
        "author": "",
        "difficulty": "",
    }


async def test_ai_flow(client, monkeypatch):
    async def fake_call(cfg, task):
        assert cfg["api_key"] == "secret-123"
        return {
            "problem": _problem(),
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cost": 0.02, "currency": "USD"},
        }

    monkeypatch.setattr(ai_service, "call_model", fake_call)
    await login(client)

    r = await client.put("/api/ai/model-config", json=CFG)
    assert r.status_code == 200
    assert r.json()["data"]["api_key_configured"] is True
    assert "secret-123" not in r.text

    # 密钥不得通过查询接口返回
    r = await client.get("/api/ai/model-config")
    assert r.status_code == 200
    assert "secret-123" not in r.text

    r = await client.post("/api/ai/problem-tasks/", json={"requirement": "两数之和"})
    assert r.status_code == 200
    tid = r.json()["data"]["task_id"]
    assert r.json()["data"]["status"] == "pending"

    data = None
    for _ in range(200):
        r = await client.get(f"/api/ai/problem-tasks/{tid}")
        data = r.json()["data"]
        if data["status"] in ("completed", "failed"):
            break
        await asyncio.sleep(0.05)
    assert data["status"] == "completed"
    assert data["result"]["id"] == "ai_1"
    assert data["usage"]["total_tokens"] == 15


async def test_ai_cancel(client, monkeypatch):
    async def hanging(cfg, task):
        await asyncio.sleep(3600)
        return {"problem": _problem(), "usage": {}}

    monkeypatch.setattr(ai_service, "call_model", hanging)
    await login(client)
    await client.put("/api/ai/model-config", json=CFG)
    r = await client.post("/api/ai/problem-tasks/", json={"requirement": "x"})
    tid = r.json()["data"]["task_id"]

    await asyncio.sleep(0.1)
    r = await client.put(f"/api/ai/problem-tasks/{tid}/cancel")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "cancelled"

    data = None
    for _ in range(50):
        r = await client.get(f"/api/ai/problem-tasks/{tid}")
        data = r.json()["data"]
        if data["status"] == "cancelled":
            break
        await asyncio.sleep(0.05)
    assert data["status"] == "cancelled"


async def test_ai_requires_config(client):
    await login(client)
    r = await client.post("/api/ai/problem-tasks/", json={"requirement": "x"})
    assert r.status_code == 400


async def test_build_usage():
    usage = {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500}
    cfg = {"price_unit": 1000, "input_price": 1.0, "output_price": 2.0}
    u = ai_service._build_usage(usage, cfg)
    assert u["input_tokens"] == 1000
    assert u["output_tokens"] == 500
    assert u["total_tokens"] == 1500
    assert u["cost"] == 1000 / 1000 * 1.0 + 500 / 1000 * 2.0
