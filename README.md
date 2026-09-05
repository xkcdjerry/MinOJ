# OJ 在线评测系统

程序设计训练（Python）实验二大作业：一个基于 **FastAPI（全异步）+ Streamlit** 的小型 Online Judge 系统，覆盖题目管理、代码评测、评测列表、用户管理、日志与权限、前端交互，以及进阶的 AI 智能命题。

## 功能模块

| 模块 | 内容 |
| --- | --- |
| Step 1 题目管理 | 题目配置加载、字段校验、增删改查（删除级联清理相关提交与日志） |
| Step 2 评测控制 | Python/C++ 评测、编译运行、时间/内存限制、输出比对、动态注册语言 |
| Step 3 评测列表 | 提交列表筛选与分页、单个详情、重新评测 |
| Step 4 用户管理 | 注册、登录/登出、初始管理员、权限管理、用户列表 |
| Step 5 日志与权限 | 测试点明细、日志可见性、访问审计 |
| Step 6 前端交互 | Streamlit 页面：用户/题目/评测三组页面 |
| Advance AI 命题 | 模型配置、命题任务、实时进度、中断、Token 用量与费用 |

## 技术要点

- **全异步**：所有 API 均为 `async def`（FastAPI），评测通过 `asyncio.create_task` 后台执行、子进程用 `asyncio.create_subprocess_exec`。
- **存储**：本地 JSON 文件（每题/每用户/每提交一个文件），内存缓存 + 写穿持久化，重启不丢数据。
- **认证**：Starlette `SessionMiddleware` + Cookie；密码 bcrypt 哈希；初始管理员 `admin / admintestpassword`。
- **资源限制**：时间用 `asyncio.wait_for`，内存用 `psutil` 后台线程轮询 RSS；超限判 TLE/MLE。
- **安全**：密码与 AI 模型密钥不落日志、不随查询/错误/SSE 返回；AI 的 provider/model/key 不写死在代码中。

## 环境要求

- Python 3.10+（推荐 3.10）
- 评测默认语言：`python3`、`g++`（评分环境为 Linux）

## 安装

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## 运行

启动后端（默认 `http://127.0.0.1:8000`）：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

启动前端（另开一个终端，默认 `http://localhost:8501`）：

```bash
streamlit run frontend/app.py
```

接口文档（FastAPI 自动生成）：`http://127.0.0.1:8000/docs`

## 测试

```bash
pytest
```

测试使用独立的临时数据目录，并通过 `/api/reset/` 在每个用例前复位环境。

## 目录结构

```
app/
  main.py           # FastAPI 入口、SessionMiddleware、异常处理器
  config.py         # 路径与运行参数
  errors.py         # 统一错误响应（{code,msg,data}）
  schemas.py        # Pydantic 模型
  storage.py        # 异步 JSON 文件存储
  deps.py           # 认证依赖（当前用户/管理员）
  bootstrap.py      # 启动引导（初始管理员 + 默认语言）
  routers/          # 各模块路由
  services/         # 业务逻辑（judge 评测引擎、ai 命题等）
frontend/
  app.py            # Streamlit 前端
  api_client.py     # 统一 API 客户端
tests/              # pytest 测试
docs/               # 实验报告提纲、AI 使用说明
```

## 主要接口

基础模块接口严格遵循课程 `api.md`（路径、参数、状态码、`{code,msg,data}` 响应结构、异常优先级 401>403>400>429>409>404>500）：

- 题目：`GET/POST /api/problems/`、`GET/PUT/DELETE /api/problems/{id}`
- 评测：`POST /api/submissions/`、`GET /api/submissions/`、`GET /api/submissions/{id}`、`PUT /api/submissions/{id}/rejudge`
- 语言：`POST/GET /api/languages/`
- 用户：`POST /api/auth/login`、`POST /api/auth/logout`、`POST /api/users/`、`POST /api/users/admin`、`GET /api/users/`、`GET /api/users/{id}`、`PUT /api/users/{id}/role`
- 日志：`GET /api/submissions/{id}/log`、`PUT /api/problems/{id}/log_visibility`、`GET /api/logs/access/`
- 重置：`POST /api/reset/`
- AI：`PUT/GET /api/ai/model-config`、`POST /api/ai/problem-tasks/`、`GET /api/ai/problem-tasks/{id}`、`GET /api/ai/problem-tasks/{id}/events`（SSE）、`PUT /api/ai/problem-tasks/{id}/cancel`

## 助教澄清事项（已实现）

1. 普通用户查看题目详情时返回 `testcases`。
2. 题目修改允许所有普通登录用户，仅删除限管理员。
3. 题目/测试点修改后，已通过提交不自动重新评测。
4. 删除题目级联删除其测试点、提交、judge 日志与访问审计。
5. 访问审计 `action` 字段值为 `view_logs`。
