"""OJ 前端（Streamlit）。

仅通过 REST API 与 FastAPI 后端交互，不直接读写后端数据。
运行：streamlit run frontend/app.py
"""
import json
import time

import streamlit as st

from api_client import ApiClient

st.set_page_config(page_title="OJ 系统", page_icon="🧩", layout="wide")

BASE_URL = st.session_state.get("base_url", "http://127.0.0.1:8000")
if "client" not in st.session_state:
    st.session_state.client = ApiClient(BASE_URL)
if "user" not in st.session_state:
    st.session_state.user = None  # {"user_id","username","role"}

client: ApiClient = st.session_state.client


def flash(status, body):
    if status is None:
        st.error(body.get("msg", "连接失败"))
    elif 200 <= status < 300 and body.get("code") == 200:
        st.success(body.get("msg", "success"))
        return True
    else:
        st.error(f"[{body.get('code')}] {body.get('msg')}")
    return False


def require_login():
    if st.session_state.user is None:
        st.warning("请先登录。")
        return False
    return True


def go(page: str):
    """按钮触发的导航：先把目标页暂存，再重跑。

    不能直接写 st.session_state.page，因为 radio 已把 page 绑定为 widget key，
    在其实例化之后修改会抛 StreamlitWidgetAlreadyInstantiatedError。
    """
    st.session_state.nav_target = page
    st.rerun()


def parse_json_field(text: str, label: str, default=None):
    if default is None:
        default = []
    try:
        val = json.loads(text)
    except Exception:
        st.error(f"{label} 必须是合法 JSON。")
        return None
    return val


# ---------- 页面：登录 / 注册 ----------
def page_login():
    st.subheader("登录 / 注册")
    tab_login, tab_register = st.tabs(["登录", "注册"])
    with tab_login:
        with st.form("login_form"):
            username = st.text_input("用户名")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录")
        if submitted:
            status, body = client.login(username, password)
            if flash(status, body):
                st.session_state.user = body["data"]
                go("题目列表")
    with tab_register:
        with st.form("register_form"):
            username = st.text_input("用户名", key="reg_user")
            password = st.text_input("密码", type="password", key="reg_pass")
            submitted = st.form_submit_button("注册")
        if submitted:
            status, body = client.register(username, password)
            flash(status, body)


# ---------- 页面：个人信息 ----------
def page_profile():
    st.subheader("个人信息")
    if not require_login():
        return
    user = st.session_state.user
    status, body = client.get_user(user["user_id"])
    if status and body.get("code") == 200:
        st.json(body["data"])
    else:
        flash(status, body)


# ---------- 页面：用户管理（管理员） ----------
def page_user_admin():
    st.subheader("用户管理")
    if not require_login() or st.session_state.user["role"] != "admin":
        st.warning("仅管理员可访问。")
        return
    status, body = client.list_users()
    if not (status and body.get("code") == 200):
        flash(status, body)
        return
    users = body["data"]["users"]
    st.write(f"共 {body['data']['total']} 位用户")
    st.dataframe(users, use_container_width=True)

    st.markdown("**变更角色**")
    with st.form("role_form"):
        user_id = st.text_input("用户 ID")
        role = st.selectbox("角色", ["user", "admin", "banned"])
        submitted = st.form_submit_button("更新角色")
    if submitted:
        status, body = client.set_role(user_id, role)
        if flash(status, body):
            st.rerun()

    st.markdown("**创建管理员**")
    with st.form("create_admin_form"):
        username = st.text_input("用户名", key="adm_user")
        password = st.text_input("密码", type="password", key="adm_pass")
        submitted = st.form_submit_button("创建")
    if submitted:
        status, body = client.create_admin(username, password)
        if flash(status, body):
            st.rerun()


# ---------- 页面：题目列表 ----------
def page_problems():
    st.subheader("题目列表")
    if not require_login():
        return
    status, body = client.list_problems()
    if not (status and body.get("code") == 200):
        flash(status, body)
        return
    problems = body["data"]
    for p in problems:
        col1, col2 = st.columns([3, 1])
        col1.markdown(f"**{p['id']}**  {p['title']}")
        if col2.button("查看", key=f"view_{p['id']}"):
            st.session_state.view_problem = p["id"]
            go("题目详情")
    st.divider()
    if st.button("➕ 新增题目"):
        st.session_state.edit_problem = None
        st.session_state.pop("ai_import", None)
        go("编辑题目")


# ---------- 页面：题目详情 / 编辑 ----------
def page_problem_detail():
    if not require_login():
        return
    pid = st.session_state.get("view_problem")
    if not pid:
        st.info("请从题目列表选择一个题目。")
        return
    status, body = client.get_problem(pid)
    if not (status and body.get("code") == 200):
        flash(status, body)
        return
    p = body["data"]
    st.subheader(f"{p['id']} - {p['title']}")
    st.markdown(f"**难度**: {p.get('difficulty') or '—'}　**标签**: {', '.join(p.get('tags') or [])}")
    st.markdown(f"**限制**: {p['time_limit']}s / {p['memory_limit']}MB")
    st.markdown("**题目描述**")
    st.write(p["description"])
    st.markdown("**输入格式**"); st.write(p["input_description"])
    st.markdown("**输出格式**"); st.write(p["output_description"])
    st.markdown("**样例**")
    for s in p.get("samples", []):
        st.code(f"输入: {s['input']}\n输出: {s['output']}")
    st.markdown("**数据范围**"); st.write(p["constraints"])
    if p.get("hint"):
        st.markdown("**提示**"); st.write(p["hint"])

    if st.button("✏️ 编辑此题"):
        st.session_state.edit_problem = pid
        go("编辑题目")
    if st.session_state.user["role"] == "admin":
        if st.button("🗑 删除此题"):
            status, body = client.delete_problem(pid)
            if flash(status, body):
                st.session_state.pop("view_problem", None)
                go("题目列表")


# ---------- 页面：新增 / 编辑题目 ----------
def problem_form(initial=None):
    is_edit = initial is not None
    st.subheader("编辑题目" if is_edit else "新增题目")
    with st.form("problem_form"):
        pid = st.text_input("题目 ID", value=initial.get("id", "") if initial else "")
        title = st.text_input("标题", value=initial.get("title", "") if initial else "")
        description = st.text_area("题目描述", value=initial.get("description", "") if initial else "")
        input_desc = st.text_area("输入格式", value=initial.get("input_description", "") if initial else "")
        output_desc = st.text_area("输出格式", value=initial.get("output_description", "") if initial else "")
        samples = st.text_area(
            "样例（JSON 数组）", value=json.dumps(initial.get("samples", []), ensure_ascii=False) if initial else '[{"input": "", "output": ""}]'
        )
        constraints = st.text_area("数据范围", value=initial.get("constraints", "") if initial else "")
        testcases = st.text_area(
            "测试点（JSON 数组）", value=json.dumps(initial.get("testcases", []), ensure_ascii=False) if initial else '[{"input": "", "output": ""}]'
        )
        hint = st.text_input("提示", value=initial.get("hint", "") if initial else "")
        source = st.text_input("来源", value=initial.get("source", "") if initial else "")
        tags = st.text_input("标签（JSON 数组）", value=json.dumps(initial.get("tags", []), ensure_ascii=False) if initial else '[]')
        author = st.text_input("作者", value=initial.get("author", "") if initial else "")
        difficulty = st.text_input("难度", value=initial.get("difficulty", "") if initial else "")
        col1, col2 = st.columns(2)
        time_limit = col1.number_input("时间限制(s)", min_value=0.0, value=float(initial.get("time_limit", 3.0)) if initial else 3.0)
        memory_limit = col2.number_input("内存限制(MB)", min_value=1, value=int(initial.get("memory_limit", 128)) if initial else 128)
        submitted = st.form_submit_button("保存" if is_edit else "创建")

    if submitted:
        if not (pid and title and description and constraints):
            st.error("ID/标题/描述/数据范围为必填。")
            return
        samples_val = parse_json_field(samples, "样例")
        testcases_val = parse_json_field(testcases, "测试点")
        tags_val = parse_json_field(tags, "标签")
        if samples_val is None or testcases_val is None or tags_val is None:
            return
        problem = {
            "id": pid, "title": title, "description": description,
            "input_description": input_desc, "output_description": output_desc,
            "samples": samples_val, "constraints": constraints, "testcases": testcases_val,
            "hint": hint, "source": source, "tags": tags_val,
            "time_limit": time_limit, "memory_limit": int(memory_limit),
            "author": author, "difficulty": difficulty,
        }
        if is_edit:
            status, body = client.update_problem(pid, problem)
        else:
            status, body = client.create_problem(problem)
        if flash(status, body):
            st.session_state.view_problem = pid
            st.session_state.pop("edit_problem", None)
            st.session_state.pop("ai_import", None)
            go("题目详情")


def page_problem_edit():
    if not require_login():
        return
    pid = st.session_state.get("edit_problem")
    initial = None
    if pid:
        status, body = client.get_problem(pid)
        if status and body.get("code") == 200:
            initial = body["data"]
    elif st.session_state.get("ai_import"):
        initial = st.session_state["ai_import"]
    problem_form(initial)


# ---------- 页面：提交评测 ----------
def page_submit():
    st.subheader("提交代码")
    if not require_login():
        return
    status, problems = client.list_problems()
    if not (status and problems.get("code") == 200):
        flash(status, problems)
        return
    status, langs = client.list_languages()
    if not (status and langs.get("code") == 200):
        flash(status, langs)
        return
    problem_ids = [p["id"] for p in problems["data"]]
    lang_names = langs["data"]["name"]
    if not problem_ids or not lang_names:
        st.info("暂无题目或语言，请先创建题目。")
        return

    with st.form("submit_form"):
        problem_id = st.selectbox("题目", problem_ids)
        language = st.selectbox("语言", lang_names)
        code = st.text_area("代码", height=260)
        submitted = st.form_submit_button("提交")
    if submitted:
        if not code.strip():
            st.error("代码不能为空。")
            return
        status, body = client.submit(problem_id, language, code)
        if flash(status, body):
            st.session_state.watch_submission = body["data"]["submission_id"]
            go("评测详情")

    # 提交记录
    st.divider()
    st.markdown("**我的提交记录**")
    status, body = client.list_submissions({"user_id": st.session_state.user["user_id"]})
    if status and body.get("code") == 200:
        subs = body["data"]["submissions"]
        if subs:
            for s in subs:
                col1, col2 = st.columns([4, 1])
                col1.write(f"#{s['submission_id']}  {s.get('status')}  score={s.get('score')}/{s.get('counts')}")
                if col2.button("详情", key=f"sub_{s['submission_id']}"):
                    st.session_state.watch_submission = s["submission_id"]
                    go("评测详情")
        else:
            st.write("暂无提交。")


# ---------- 页面：评测详情 ----------
def page_submission_detail():
    st.subheader("评测详情")
    if not require_login():
        return
    sid = st.session_state.get("watch_submission")
    if not sid:
        st.info("请先提交代码或选择一条提交记录。")
        return
    status, body = client.get_submission(sid)
    if not (status and body.get("code") == 200):
        flash(status, body)
        return
    data = body["data"]
    st.write(
        f"**Submission #{data['submission_id']}**　题目 `{data.get('problem_id')}`　"
        f"语言 `{data.get('language')}`　状态: `{data['status']}`"
    )
    if data.get("code"):
        st.markdown("**提交代码**")
        st.code(data["code"], language=data.get("language") or "python")
    if data["status"] == "pending":
        st.info("评测进行中…")
        if st.button("🔄 刷新状态"):
            st.rerun()
        time.sleep(1)
        st.rerun()
    st.write(f"得分: {data.get('score')} / {data.get('counts')}")
    st.markdown("**编译信息**"); st.json(data.get("compile_info"))
    st.markdown("**运行信息**"); st.json(data.get("run_info"))
    if data.get("error_info"):
        st.markdown("**错误信息**"); st.code(data["error_info"])

    status, body = client.get_log(sid)
    if status and body.get("code") == 200 and body["data"].get("details"):
        st.markdown("**测试点明细**")
        st.dataframe(body["data"]["details"], use_container_width=True)

    if st.session_state.user["role"] == "admin":
        if st.button("🔁 重新评测"):
            status, body = client.rejudge(sid)
            flash(status, body)


# ---------- 页面：AI 智能命题 ----------
def page_ai():
    st.subheader("AI 智能命题")
    if not require_login():
        return

    st.markdown("**模型配置**")
    with st.expander("配置模型（provider_url / model / api_key / 价格）", expanded=True):
        with st.form("ai_config_form"):
            provider_url = st.text_input("Provider URL", value="https://model-provider.example/v1")
            model = st.text_input("模型名称")
            api_key = st.text_input("API Key", type="password")
            col1, col2, col3 = st.columns(3)
            input_price = col1.number_input("输入单价", min_value=0.0, value=1.0)
            output_price = col2.number_input("输出单价", min_value=0.0, value=2.0)
            price_unit = col3.number_input("计价单位", min_value=1, value=1000000)
            submitted = st.form_submit_button("保存配置")
        if submitted:
            status, body = client.ai_set_config({
                "provider_url": provider_url, "model": model, "api_key": api_key,
                "input_price": input_price, "output_price": output_price, "price_unit": int(price_unit),
            })
            flash(status, body)

    st.markdown("**命题需求**")
    with st.form("ai_task_form"):
        requirement = st.text_area("需求（知识点、难度、约束等）")
        problem_ids = []
        status, body = client.list_problems()
        if status and body.get("code") == 200:
            problem_ids = [p["id"] for p in body["data"]]
        problem_id = st.selectbox("参考/修改已有题目（可选）", ["（无）"] + problem_ids)
        submitted = st.form_submit_button("开始命题")
    if submitted:
        ref = None if problem_id == "（无）" else problem_id
        status, body = client.ai_create_task(requirement, ref)
        if flash(status, body):
            st.session_state.ai_task = body["data"]["task_id"]

    tid = st.session_state.get("ai_task")
    if tid:
        st.divider()
        st.write(f"任务 `{tid}`")
        placeholder = st.empty()
        for _ in range(120):
            status, body = client.ai_get_task(tid)
            if not (status and body.get("code") == 200):
                break
            t = body["data"]
            placeholder.write(f"状态: `{t['status']}`　进度: {t.get('progress')}")
            if t.get("usage"):
                placeholder.write(f"Tokens: {t['usage']['total_tokens']}　费用: {t['usage']['cost']} {t['usage']['currency']}")
            if t["status"] in ("completed", "failed", "cancelled"):
                break
            time.sleep(1)
        status, body = client.ai_get_task(tid)
        t = body["data"] if status and body.get("code") == 200 else {}
        if t.get("status") == "completed" and t.get("result"):
            st.success("命题完成")
            st.json(t["result"])
            if st.button("✅ 导入到题目新增"):
                st.session_state.edit_problem = None
                st.session_state.ai_import = t["result"]
                go("编辑题目")
        elif t.get("status") == "failed":
            st.error("命题失败，请检查模型配置与返回。")
        if t.get("status") in ("pending", "running"):
            if st.button("⛔ 中断任务"):
                status, body = client.ai_cancel_task(tid)
                flash(status, body)


def main():
    # 处理按钮触发的导航请求（必须在 radio 实例化之前写入 widget key）
    if "nav_target" in st.session_state:
        st.session_state.page = st.session_state.nav_target
        del st.session_state.nav_target

    user = st.session_state.user

    with st.sidebar:
        st.title("OJ 系统")
        if user:
            st.write(f"当前用户：**{user['username']}**（{user['role']}）")
            if st.button("退出登录"):
                client.logout()
                st.session_state.user = None
                st.session_state.page = "登录 / 注册"
                st.session_state.pop("view_problem", None)
                st.session_state.pop("edit_problem", None)
                st.rerun()
        else:
            st.write("未登录")

        # 侧边栏单选是唯一导航来源；题目详情/编辑作为可选导航项动态出现
        pages = ["登录 / 注册"]
        if user:
            pages += ["个人信息", "题目列表", "提交代码", "评测详情", "AI 智能命题"]
            if st.session_state.get("view_problem"):
                pages.append("题目详情")
            if "edit_problem" in st.session_state:
                pages.append("编辑题目")
            if user["role"] == "admin":
                pages.append("用户管理")

        if "page" not in st.session_state or st.session_state.page not in pages:
            st.session_state.page = "登录 / 注册"
        st.radio("导航", pages, key="page")

    page = st.session_state.page
    if page == "登录 / 注册":
        page_login()
    elif page == "个人信息":
        page_profile()
    elif page == "题目列表":
        page_problems()
    elif page == "题目详情":
        page_problem_detail()
    elif page == "编辑题目":
        page_problem_edit()
    elif page == "提交代码":
        page_submit()
    elif page == "评测详情":
        page_submission_detail()
    elif page == "AI 智能命题":
        page_ai()
    elif page == "用户管理":
        page_user_admin()


main()
