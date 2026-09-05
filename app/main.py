"""FastAPI 应用入口。

- 所有路由均为 async def；
- SessionMiddleware 提供 Cookie 会话；
- import 时执行一次 bootstrap（加载数据 + 初始管理员 + 默认语言）。
"""
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app import config
from app.bootstrap import bootstrap_sync
from app.errors import register_exception_handlers
from app.routers import ai, auth, languages, logs, problems, reset, submissions, users

bootstrap_sync()

app = FastAPI(title="Online Judge System")
app.add_middleware(SessionMiddleware, secret_key=config.SECRET_KEY)
register_exception_handlers(app)

for r in (
    problems.router,
    languages.router,
    submissions.router,
    auth.router,
    users.router,
    logs.router,
    reset.router,
    ai.router,
):
    app.include_router(r)
