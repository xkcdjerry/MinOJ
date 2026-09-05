"""测试夹具：临时数据目录 + httpx ASGI 客户端 + 自动重置。"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

# 确保项目根目录在 sys.path 上，使 `app` 包可被导入（无论 pytest 从何处启动）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 必须在导入 app 之前设置，避免污染真实 data 目录
# 测试数据目录放在项目根目录下（沙箱仅允许写工作区），并在 .gitignore 中忽略
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEST_DATA_DIR = _PROJECT_ROOT / f".pytest_oj_{uuid.uuid4().hex[:8]}"
os.makedirs(_TEST_DATA_DIR, exist_ok=True)
os.environ["OJ_DATA_DIR"] = str(_TEST_DATA_DIR)
os.environ["OJ_SECRET_KEY"] = "test-secret-key"

import httpx
import pytest
from httpx import ASGITransport

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def _reset():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        await c.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
        await c.post("/api/reset/")
        # 重置会退出登录，重新登录后注册一个确定可用的 python 语言用于评测
        await c.post("/api/auth/login", json={"username": "admin", "password": "admintestpassword"})
        await c.post("/api/languages/", json={
            "name": "python",
            "file_ext": ".py",
            "compile_cmd": None,
            "run_cmd": f'"{sys.executable}" {{src}}',
            "time_limit": 5.0,
            "memory_limit": 512,
        })


async def login(client, username="admin", password="admintestpassword"):
    return await client.post("/api/auth/login", json={"username": username, "password": password})


async def register(client, username, password):
    return await client.post("/api/users/", json={"username": username, "password": password})


async def wait_submission(client, submission_id, max_tries=200):
    data = None
    for _ in range(max_tries):
        r = await client.get(f"/api/submissions/{submission_id}")
        data = r.json()["data"]
        if data["status"] != "pending":
            return data
        await asyncio.sleep(0.05)
    return data
