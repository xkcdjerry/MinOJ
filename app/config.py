"""集中管理路径与运行参数。数据目录可通过环境变量 OJ_DATA_DIR 覆盖（测试用）。"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.environ.get("OJ_DATA_DIR", os.path.join(BASE_DIR, "data"))
SECRET_KEY = os.environ.get("OJ_SECRET_KEY", "oj-dev-secret-key-change-me")

# 评测资源限制的系统默认值（时间：秒，内存：MB）
DEFAULT_TIME_LIMIT = 3.0
DEFAULT_MEMORY_LIMIT = 128
COMPILE_TIMEOUT = 20.0

# 提交频率限制：1 分钟内最多 SUBMIT_RATE_LIMIT 次
SUBMIT_RATE_LIMIT = 3
SUBMIT_RATE_WINDOW = 60  # 秒

# 初始管理员账户
INITIAL_ADMIN_USERNAME = "admin"
INITIAL_ADMIN_PASSWORD = "admintestpassword"

# 访问审计中唯一的 action 取值（与 api.md 一致：view_logs）
ACCESS_LOG_ACTION = "view_logs"

# 子目录 / 文件
WORK_DIR = os.path.join(DATA_DIR, "work")  # 评测临时工作目录
PROBLEMS_DIR = os.path.join(DATA_DIR, "problems")
USERS_DIR = os.path.join(DATA_DIR, "users")
SUBMISSIONS_DIR = os.path.join(DATA_DIR, "submissions")
LANGUAGES_DIR = os.path.join(DATA_DIR, "languages")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
AI_DIR = os.path.join(DATA_DIR, "ai")
AI_TASKS_DIR = os.path.join(AI_DIR, "tasks")
ACCESS_LOG_FILE = os.path.join(LOGS_DIR, "access.json")
AI_CONFIG_FILE = os.path.join(AI_DIR, "config.json")
