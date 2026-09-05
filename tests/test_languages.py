"""Step2 语言注册/查询测试。"""
from conftest import login


async def test_languages_list_and_register(client):
    # 未登录也可查看语言列表
    r = await client.get("/api/languages/")
    assert r.status_code == 200
    assert "python" in r.json()["data"]["name"]

    # 注册需要登录
    r = await client.post("/api/languages/", json={
        "name": "go", "file_ext": ".go", "run_cmd": "go run {src}",
    })
    assert r.status_code == 401

    await login(client)
    r = await client.post("/api/languages/", json={
        "name": "go", "file_ext": ".go", "run_cmd": "go run {src}",
    })
    assert r.status_code == 200
    assert r.json()["data"] == {"name": "go"}

    r = await client.get("/api/languages/")
    assert "go" in r.json()["data"]["name"]

    # 重复注册覆盖
    r = await client.post("/api/languages/", json={
        "name": "go", "file_ext": ".go", "run_cmd": "go run {src}", "time_limit": 2.0,
    })
    assert r.status_code == 200
