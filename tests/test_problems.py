"""Step1 题目管理测试。"""
from conftest import login, register, wait_submission


def _payload(pid="p1", **overrides):
    p = {
        "id": pid,
        "title": "A+B",
        "description": "sum",
        "input_description": "two ints",
        "output_description": "sum",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "a,b<=10",
        "testcases": [{"input": "1 2", "output": "3"}],
    }
    p.update(overrides)
    return p


async def test_problem_crud_and_permissions(client):
    await login(client)
    r = await client.post("/api/problems/", json=_payload())
    assert r.status_code == 200
    assert r.json()["data"] == {"id": "p1"}

    # 重复 id -> 409
    r = await client.post("/api/problems/", json=_payload())
    assert r.status_code == 409

    # 列表
    r = await client.get("/api/problems/")
    assert r.json()["data"] == [{"id": "p1", "title": "A+B"}]

    # 详情包含 testcases
    r = await client.get("/api/problems/p1")
    assert r.json()["data"]["testcases"] == [{"input": "1 2", "output": "3"}]

    # 编辑（普通用户也可编辑）
    await register(client, "alice", "password1")
    await login(client, "alice", "password1")
    r = await client.put("/api/problems/p1", json=_payload(pid="p1", title="A+B v2"))
    assert r.status_code == 200
    r = await client.get("/api/problems/p1")
    assert r.json()["data"]["title"] == "A+B v2"

    # 普通用户不可删除 -> 403
    r = await client.delete("/api/problems/p1")
    assert r.status_code == 403

    # 管理员可删除 -> 200
    await login(client)
    r = await client.delete("/api/problems/p1")
    assert r.status_code == 200
    r = await client.get("/api/problems/p1")
    assert r.status_code == 404


async def test_problem_requires_login(client):
    r = await client.get("/api/problems/")
    assert r.status_code == 401
    r = await client.post("/api/problems/", json=_payload())
    assert r.status_code == 401


async def test_problem_validation(client):
    await login(client)
    # 缺少字段 -> 400
    r = await client.post("/api/problems/", json={"id": "x"})
    assert r.status_code == 400
    # 空标题 -> 400
    r = await client.post("/api/problems/", json=_payload(pid="bad", title=""))
    assert r.status_code == 400
    # 空 testcases -> 400
    r = await client.post("/api/problems/", json=_payload(pid="bad2", testcases=[]))
    assert r.status_code == 400
    # 编辑时 id 不一致 -> 400
    await client.post("/api/problems/", json=_payload(pid="p2"))
    r = await client.put("/api/problems/p2", json=_payload(pid="other"))
    assert r.status_code == 400


async def test_problem_delete_cascades(client):
    await login(client)
    await client.post("/api/problems/", json=_payload(pid="p1"))
    # 产生一条提交并等待评测完成（评测日志内嵌于提交）
    r = await client.post("/api/submissions/", json={
        "problem_id": "p1", "language": "python", "code": "print(3)",
    })
    sid = r.json()["data"]["submission_id"]
    await wait_submission(client, sid)
    r = await client.delete("/api/problems/p1")
    assert r.status_code == 200
    r = await client.get("/api/submissions/", params={"problem_id": "p1"})
    assert r.json()["data"]["total"] == 0
