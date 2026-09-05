"""Step4 用户管理测试。"""
from conftest import login, register


async def test_register_and_login(client):
    r = await register(client, "alice", "password1")
    assert r.status_code == 200
    d = r.json()["data"]
    alice_id = d["user_id"]
    assert d["username"] == "alice"
    assert d["role"] == "user"
    assert d["submit_count"] == 0 and d["resolve_count"] == 0

    # 重名 -> 400
    r = await register(client, "alice", "password2")
    assert r.status_code == 400

    # 登录
    r = await login(client, "alice", "password1")
    assert r.status_code == 200
    assert r.json()["data"]["role"] == "user"

    # 错误密码 -> 401
    r = await login(client, "alice", "wrongpass")
    assert r.status_code == 401

    # 登出后未登录 -> 401
    r = await client.post("/api/auth/logout")
    assert r.status_code == 200
    r = await client.get(f"/api/users/{alice_id}")
    assert r.status_code == 401


async def test_register_validation(client):
    r = await register(client, "ab", "password1")  # 用户名过短
    assert r.status_code == 400
    r = await register(client, "alice", "123")  # 密码过短
    assert r.status_code == 400


async def test_user_info_permission(client):
    r = await register(client, "alice", "password1")
    alice_id = r.json()["data"]["user_id"]
    await register(client, "bob", "password1")
    await login(client, "alice", "password1")

    # 查看自己 -> 200
    r = await client.get(f"/api/users/{alice_id}")
    assert r.status_code == 200
    # 查看他人（admin 的 id=1）-> 403
    r = await client.get("/api/users/1")
    assert r.status_code == 403


async def test_role_change_and_banned(client):
    r = await register(client, "alice", "password1")
    alice_id = r.json()["data"]["user_id"]
    await login(client)  # admin

    # 普通用户不可改角色 -> 403
    await login(client, "alice", "password1")
    r = await client.put(f"/api/users/{alice_id}/role", json={"role": "banned"})
    assert r.status_code == 403

    # 管理员变更角色 -> 200
    await login(client)
    r = await client.put(f"/api/users/{alice_id}/role", json={"role": "banned"})
    assert r.status_code == 200
    assert r.json()["data"] == {"user_id": alice_id, "role": "banned"}

    # banned 用户登录 -> 403
    r = await login(client, "alice", "password1")
    assert r.status_code == 403

    # 无效角色 -> 400
    r = await client.put(f"/api/users/{alice_id}/role", json={"role": "super"})
    assert r.status_code == 400


async def test_user_list_admin_only(client):
    await register(client, "alice", "password1")
    # 普通用户不可查列表 -> 403
    await login(client, "alice", "password1")
    r = await client.get("/api/users/")
    assert r.status_code == 403

    # 管理员可查 -> 200
    await login(client)
    r = await client.get("/api/users/")
    assert r.status_code == 200
    assert r.json()["data"]["total"] >= 2  # admin + alice
