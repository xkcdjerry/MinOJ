"""启动引导（同步，import 时执行一次）：加载数据、创建初始管理员与默认语言。"""
import sys
from datetime import datetime

import bcrypt

from app import config, storage


def default_languages() -> dict:
    # python 评测命令使用当前解释器 sys.executable（加引号以防路径含空格）：
    # - Linux：即运行服务的 python3；
    # - Windows：避免 python3 是 Microsoft Store 占位符（exit code 9009）导致 RE；
    # - venv：指向虚拟环境内解释器，依赖一致。
    py = f'"{sys.executable}"'
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

    # 内置默认语言（python/cpp）每次启动都刷新为正确命令，
    # 避免旧数据里残留失效命令（如 Windows 的 python3 商店占位符）。
    for name, lang in default_languages().items():
        storage.db.languages.put_sync(name, lang)
