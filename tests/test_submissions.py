"""Step2/3 评测提交测试。"""
import asyncio

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
        "testcases": [{"input": "1 2", "output": "3"}, {"input": "10 20", "output": "30"}],
    })


async def test_submit_ac_wa(client):
    await login(client)
    await _add_sum_problem(client)

    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python",
        "code": "a, b = map(int, input().split())\nprint(a + b)",
    })
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "pending"
    sid = r.json()["data"]["submission_id"]

    data = await wait_submission(client, sid)
    assert data["status"] == "success"
    assert data["score"] == 20
    assert data["counts"] == 20

    # WA
    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python", "code": "print(0)",
    })
    data = await wait_submission(client, r.json()["data"]["submission_id"])
    assert data["status"] == "success"
    assert data["score"] == 0


async def test_submit_errors(client):
    await login(client)
    await _add_sum_problem(client)

    r = await client.post("/api/submissions/", json={
        "problem_id": "nope", "language": "python", "code": "print(1)",
    })
    assert r.status_code == 404

    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "nolang", "code": "print(1)",
    })
    assert r.status_code == 404

    r = await client.post("/api/submissions/", json={"problem_id": "sum", "language": "python"})
    assert r.status_code == 400


async def test_rate_limit(client):
    await login(client)
    await _add_sum_problem(client)
    code = "print(1)"
    for _ in range(3):
        r = await client.post("/api/submissions/", json={
            "problem_id": "sum", "language": "python", "code": code,
        })
        assert r.status_code == 200
    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python", "code": code,
    })
    assert r.status_code == 429


async def test_list_filter_and_pagination(client):
    await login(client)
    await _add_sum_problem(client)
    await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python", "code": "print(1)",
    })

    # 一级条件全空 -> 400
    r = await client.get("/api/submissions/")
    assert r.status_code == 400

    # 按 problem 查询
    r = await client.get("/api/submissions/", params={"problem_id": "sum"})
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1

    # page 有值但 page_size 空 -> 400
    r = await client.get("/api/submissions/", params={"problem_id": "sum", "page": 1})
    assert r.status_code == 400

    # 普通用户只能看自己的记录
    await register(client, "bob", "password1")
    await login(client, "bob", "password1")
    r = await client.get("/api/submissions/", params={"problem_id": "sum"})
    assert r.json()["data"]["total"] == 0


async def test_rejudge(client):
    await login(client)
    await _add_sum_problem(client)
    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python", "code": "print(0)",
    })
    sid = r.json()["data"]["submission_id"]
    await wait_submission(client, sid)

    # 普通用户不可重评
    await register(client, "carol", "password1")
    await login(client, "carol", "password1")
    r = await client.put(f"/api/submissions/{sid}/rejudge")
    assert r.status_code == 403

    await login(client)
    r = await client.put(f"/api/submissions/{sid}/rejudge")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "pending"
    data = await wait_submission(client, sid)
    assert data["status"] == "success"
