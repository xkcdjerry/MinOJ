"""Step5 日志与权限测试。

覆盖需求：
- public_cases=False：提交者本人可访问自己的日志（200），但不能看到测试点明细
  details（无 AC/WA 状态、耗时、内存），只能看到 score 与 counts；其他已登录普通
  用户访问返回 403。
- public_cases=True：提交者本人与其他已登录普通用户都能看到 details（含每个测试点
  的状态、耗时、内存），以及 score、counts。
- 管理员不受 public_cases 影响，始终可查看完整日志。
- 日志公开不会同时开放用户代码、编译信息等 Step 2/3 的提交详情。
"""
from conftest import login, register, wait_submission

CORRECT_CODE = "a, b = map(int, input().split())\nprint(a + b)"

# 每个测试点 10 分，两个测试点 => counts == 20
EXPECTED_COUNTS = 20
EXPECTED_SCORE = 20
VALID_RESULTS = {"AC", "WA", "TLE", "MLE", "RE", "CE"}


async def _add_sum_problem(client):
    await client.post("/api/problems/", json={
        "id": "sum",
        "title": "A+B",
        "description": "sum",
        "input_description": "two ints",
        "output_description": "sum",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "a,b<=10",
        "testcases": [
            {"input": "1 2", "output": "3"},
            {"input": "10 20", "output": "30"},
        ],
    })


async def _submit_and_wait(client, code=CORRECT_CODE):
    """以当前登录用户提交，并等待评测完成，返回 submission_id。"""
    r = await client.post("/api/submissions/", json={
        "problem_id": "sum", "language": "python", "code": code,
    })
    sid = r.json()["data"]["submission_id"]
    await wait_submission(client, sid)
    return sid


def _assert_full_log(data):
    """断言「完整日志」：details 含每个测试点的 result/time/memory，且 score/counts 可见。"""
    assert data["details"] is not None
    assert data["score"] == EXPECTED_SCORE
    assert data["counts"] == EXPECTED_COUNTS

    details = data["details"]
    assert len(details) == 2
    for d in details:
        assert d["result"] in VALID_RESULTS  # AC/WA 等状态
        assert isinstance(d["time"], (int, float))  # 耗时
        assert isinstance(d["memory"], int)  # 内存
    # 正确程序 => 每个测试点均 AC
    assert all(d["result"] == "AC" for d in details)


async def _make_owner_submission(client):
    """准备环境：admin 建题，注册 alice 并以其身份提交，返回 submission_id。"""
    await login(client)
    await _add_sum_problem(client)
    await register(client, "alice", "password1")
    await login(client, "alice", "password1")
    return await _submit_and_wait(client)


async def test_owner_log_private_hides_details(client):
    """public_cases=False：非管理员提交者可访问自己日志，但看不到 details，只看 score/counts。"""
    sid = await _make_owner_submission(client)

    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["details"] is None  # 不暴露测试点明细
    assert data["score"] == EXPECTED_SCORE
    assert data["counts"] == EXPECTED_COUNTS


async def test_other_user_log_private_forbidden(client):
    """public_cases=False：其他已登录普通用户访问日志返回 403。"""
    sid = await _make_owner_submission(client)

    await register(client, "bob", "password1")
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 403


async def test_owner_log_public_shows_details(client):
    """public_cases=True：提交者本人可查看 details（含状态/耗时/内存）与 score/counts。"""
    sid = await _make_owner_submission(client)

    await login(client)
    await client.put("/api/problems/sum/log_visibility", json={"public_cases": True})

    await login(client, "alice", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    _assert_full_log(r.json()["data"])


async def test_other_user_log_public_shows_details(client):
    """public_cases=True：其他已登录普通用户也可查看 details 与 score/counts。"""
    sid = await _make_owner_submission(client)

    await login(client)
    await client.put("/api/problems/sum/log_visibility", json={"public_cases": True})

    await register(client, "bob", "password1")
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    _assert_full_log(r.json()["data"])


async def test_admin_always_full_log(client):
    """管理员（非提交者）不受 public_cases 影响，始终可查看完整日志。"""
    sid = await _make_owner_submission(client)

    # public_cases=False 时管理员可看完整日志
    await login(client)
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    _assert_full_log(r.json()["data"])

    # public_cases=True 时管理员仍可看完整日志
    await client.put("/api/problems/sum/log_visibility", json={"public_cases": True})
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    _assert_full_log(r.json()["data"])


async def test_log_never_exposes_submission_details(client):
    """日志公开不会同时开放用户代码、编译信息等 Step 2/3 提交详情。"""
    sid = await _make_owner_submission(client)

    await login(client)
    await client.put("/api/problems/sum/log_visibility", json={"public_cases": True})

    await register(client, "bob", "password1")
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    data = r.json()["data"]
    for key in ("code", "compile_info", "run_info", "error_info"):
        assert key not in data


async def test_log_audit(client):
    """审计：访问日志记录 view_logs，且包含 403 与 200 记录。"""
    sid = await _make_owner_submission(client)

    # 其他普通用户（非公开）-> 403，产生一条 403 审计
    await register(client, "bob", "password1")
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 403

    # 公开后 -> 200，产生一条 200 审计
    await login(client)
    await client.put("/api/problems/sum/log_visibility", json={"public_cases": True})
    await login(client, "bob", "password1")
    r = await client.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200

    await login(client)
    r = await client.get("/api/logs/access/")
    assert r.status_code == 200
    entries = r.json()["data"]
    assert entries, "应存在访问审计记录"
    assert all(e["action"] == "view_logs" for e in entries)
    statuses = {e["status"] for e in entries}
    assert "403" in statuses
    assert "200" in statuses
