"""异步 JSON 文件存储层。

- 每个实体一个 JSON 文件，内存缓存 + 写穿（write-through）持久化，重启不丢数据。
- 写操作使用 asyncio.Lock 串行化，文件 IO 通过 asyncio.to_thread 移出事件循环。
- 提供同步方法（*_sync）仅用于 import 时的 bootstrap 与测试隔离。
"""
import asyncio
import json
import os

import app.config as config


class JsonStore:
    """以 key -> dict 组织的集合，每个 key 落盘为 {key}.json。"""

    def __init__(self, directory: str):
        self.directory = directory
        self.data = {}
        self._lock = asyncio.Lock()

    # ---- 同步（启动/bootstrap 专用） ----
    def load(self):
        os.makedirs(self.directory, exist_ok=True)
        for fn in os.listdir(self.directory):
            if fn.endswith(".json"):
                key = fn[:-5]
                path = os.path.join(self.directory, fn)
                try:
                    with open(path, encoding="utf-8") as f:
                        self.data[key] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue

    def put_sync(self, key, value):
        self.data[key] = value
        self._write(key, value)

    def delete_sync(self, key):
        self.data.pop(key, None)
        self._delete(key)

    # ---- 异步 ----
    async def get(self, key):
        return self.data.get(key)

    async def put(self, key, value):
        async with self._lock:
            self.data[key] = value
            await asyncio.to_thread(self._write, key, value)

    async def delete(self, key):
        async with self._lock:
            self.data.pop(key, None)
            await asyncio.to_thread(self._delete, key)

    async def next_int_id(self) -> str:
        async with self._lock:
            return self._next_int_id()

    # ---- 内部 ----
    def _next_int_id(self) -> str:
        nums = [int(k) for k in self.data.keys() if str(k).isdigit()]
        return str(max(nums) + 1) if nums else "1"

    def _path(self, key):
        return os.path.join(self.directory, f"{key}.json")

    def _write(self, key, value):
        os.makedirs(self.directory, exist_ok=True)
        tmp = self._path(key) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path(key))

    def _delete(self, key):
        p = self._path(key)
        if os.path.exists(p):
            os.remove(p)


class AccessLog:
    """访问审计日志，单文件保存一个 JSON 数组。"""

    def __init__(self):
        self.entries = []
        self._lock = asyncio.Lock()

    def load(self):
        if os.path.exists(config.ACCESS_LOG_FILE):
            try:
                with open(config.ACCESS_LOG_FILE, encoding="utf-8") as f:
                    self.entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.entries = []

    async def append(self, entry):
        async with self._lock:
            self.entries.append(entry)
            await asyncio.to_thread(self._write_sync)

    async def clear(self):
        async with self._lock:
            self.entries = []
            await asyncio.to_thread(self._write_sync)

    async def remove_by_problem(self, problem_id):
        async with self._lock:
            self.entries = [e for e in self.entries if e.get("problem_id") != problem_id]
            await asyncio.to_thread(self._write_sync)

    def _write_sync(self):
        os.makedirs(config.LOGS_DIR, exist_ok=True)
        with open(config.ACCESS_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)


class ConfigFile:
    """单个 JSON 对象配置文件（如 AI 模型配置）。"""

    def __init__(self, path: str):
        self.path = path
        self.data = {}
        self._lock = asyncio.Lock()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.data = {}

    async def set(self, value):
        async with self._lock:
            self.data = value
            await asyncio.to_thread(self._write_sync)

    async def clear(self):
        async with self._lock:
            self.data = {}
            await asyncio.to_thread(self._write_sync)

    def _write_sync(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


class _Database:
    def __init__(self):
        self.problems = JsonStore(config.PROBLEMS_DIR)
        self.users = JsonStore(config.USERS_DIR)
        self.submissions = JsonStore(config.SUBMISSIONS_DIR)
        self.languages = JsonStore(config.LANGUAGES_DIR)
        self.ai_tasks = JsonStore(config.AI_TASKS_DIR)
        self.access_log = AccessLog()
        self.ai_config = ConfigFile(config.AI_CONFIG_FILE)

    def load(self):
        self.problems.load()
        self.users.load()
        self.submissions.load()
        self.languages.load()
        self.ai_tasks.load()
        self.access_log.load()
        self.ai_config.load()


db = _Database()
