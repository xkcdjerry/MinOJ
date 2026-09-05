"""Step5 日志与权限测试。"""
from conftest import login, register, wait_submission


async def _add_sum_problem(client):
    await client.post("/api/problems/", json={
        "id": "sum",
        "title": "A+B",
        "description": "sum",
        "input_description": "two ints",
        "output_description": "sum",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "a,b<=10",
        "testcases": [{"input": "1 2", "output": "3"}],
    })


async def test_log_visibility_and_audit(client):
    await login(client)
    await _add_sum_problem(client)
    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python", "code": "print(3)",
    })
    sid = r.json()["data"]["submission_id"]
    await wait_submission(client, sid)

    # 提交者（管理员）可查看日志
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    assert r.json()["data"]["details"] is not None
    assert r.json()["data"]["score"] == 10

    # 其他普通用户（非公开）-> 403
    await register(client, "bob", "password1")
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 403

    # 管理员设置公开后，其他用户可见 details
    await login(client)
    r = await client.put("/api/problems/sum/log_visibility", json={"public_cases": True})
    assert r.status_code == 200
    assert r.json()["data"]["public_cases"] is True
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    assert r.json()["data"]["details"] is not None

    # 审计：action 均为 view_logs，且包含 403 与 200 记录
    await login(client)
    r = await client.get("/api/logs/access/")
    assert r.status_code == 200
    entries = r.json()["data"]
    assert entries, "应存在访问审计记录"
    assert all(e["action"] == "view_logs" for e in entries)
    statuses = {e["status"] for e in entries}
    assert "403" in statuses
    assert "200" in statuses
