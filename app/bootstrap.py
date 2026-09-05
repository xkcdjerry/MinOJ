"""启动引导（同步，import 时执行一次）：加载数据、创建初始管理员与默认语言。"""
import shutil
import sys
from datetime import datetime

import bcrypt

from app import config, storage


def default_languages() -> dict:
    # Linux 评分环境用 python3；本地开发/测试在无 python3 时回退到 python / 当前解释器
    if shutil.which("python3"):
        py = "python3"
    elif shutil.which("python"):
        py = "python"
    else:
        py = sys.executable
    return {
        "python": {
            "name": "python",
            "file_ext": ".py",
            "compile_cmd": None,
            "run_cmd": f"{py} {{src}}",
            "time_limit": 3.0,
            "memory_limit": 128,
        },
        "cpp": {
            "name": "cpp",
            "file_ext": ".cpp",
            "compile_cmd": "g++ {src} -o {exe}",
            "run_cmd": "{exe}",
            "time_limit": 3.0,
            "memory_limit": 128,
        },
    }


def bootstrap_sync():
    storage.db.load()

    if not any(u.get("username") == config.INITIAL_ADMIN_USERNAME for u in storage.db.users.data.values()):
        user_id = storage.db.users._next_int_id()
        user = {
            "user_id": user_id,
            "username": config.INITIAL_ADMIN_USERNAME,
            "password_hash": bcrypt.hashpw(
                config.INITIAL_ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8"),
            "role": "admin",
            "join_time": datetime.now().strftime("%Y-%m-%d"),
            "submit_count": 0,
            "resolve_count": 0,
            "solved_problems": [],
        }
        storage.db.users.put_sync(user_id, user)

    for name, lang in default_languages().items():
        if name not in storage.db.languages.data:
            storage.db.languages.put_sync(name, lang)
