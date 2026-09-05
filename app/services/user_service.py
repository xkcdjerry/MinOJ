"""用户业务逻辑：注册、查询、权限变更、统计。"""
from datetime import datetime

import bcrypt

from app import storage
from app.errors import OJException


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def validate_username_password(username: str, password: str):
    if not (3 <= len(username) <= 40):
        raise OJException(400, "username length must be between 3 and 40")
    if len(password) < 6:
        raise OJException(400, "password length must be at least 6")


async def get_user(user_id: str):
    return await storage.db.users.get(user_id)


async def get_user_by_username(username: str):
    for u in storage.db.users.data.values():
        if u.get("username") == username:
            return u
    return None


async def create_user(username: str, password: str, role: str = "user") -> dict:
    if await get_user_by_username(username) is not None:
        raise OJException(400, "username already exists")
    user_id = await storage.db.users.next_int_id()
    user = {
        "user_id": user_id,
        "username": username,
        "password_hash": _hash(password),
        "role": role,
        "join_time": now_date(),
        "submit_count": 0,
        "resolve_count": 0,
        "solved_problems": [],
    }
    await storage.db.users.put(user_id, user)
    return user


def public_user(u: dict) -> dict:
    return {
        "user_id": u.get("user_id"),
        "username": u.get("username", ""),
        "join_time": u.get("join_time", ""),
        "role": u.get("role", "user"),
        "submit_count": u.get("submit_count", 0),
        "resolve_count": u.get("resolve_count", 0),
    }


async def list_users() -> list:
    users = [public_user(u) for u in storage.db.users.data.values()]
    users.sort(key=lambda x: int(x["user_id"]) if str(x["user_id"]).isdigit() else x["user_id"])
    return users
