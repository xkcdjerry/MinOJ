"""统一的后端 API 客户端（requests.Session 自动保存 Cookie 会话）。

每个方法返回 (http_status, body)，body 为后端 JSON（含 code/msg/data）。
"""
import requests


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _request(self, method: str, path: str, json=None, params=None):
        url = self.base_url + path
        try:
            r = self.session.request(method, url, json=json, params=params, timeout=30)
        except requests.RequestException as e:
            return None, {"code": 0, "msg": f"连接失败：{e}", "data": None}
        try:
            body = r.json()
        except ValueError:
            body = {"code": r.status_code, "msg": r.text[:200], "data": None}
        return r.status_code, body

    # ---- 认证 / 用户 ----
    def login(self, username, password):
        return self._request("POST", "/api/auth/login", json={"username": username, "password": password})

    def logout(self):
        return self._request("POST", "/api/auth/logout")

    def register(self, username, password):
        return self._request("POST", "/api/users/", json={"username": username, "password": password})

    def get_user(self, user_id):
        return self._request("GET", f"/api/users/{user_id}")

    def list_users(self, page=None, page_size=None):
        return self._request("GET", "/api/users/", params={"page": page, "page_size": page_size})

    def set_role(self, user_id, role):
        return self._request("PUT", f"/api/users/{user_id}/role", json={"role": role})

    def create_admin(self, username, password):
        return self._request("POST", "/api/users/admin", json={"username": username, "password": password})

    # ---- 题目 ----
    def list_problems(self):
        return self._request("GET", "/api/problems/")

    def get_problem(self, problem_id):
        return self._request("GET", f"/api/problems/{problem_id}")

    def create_problem(self, problem: dict):
        return self._request("POST", "/api/problems/", json=problem)

    def update_problem(self, problem_id, problem: dict):
        return self._request("PUT", f"/api/problems/{problem_id}", json=problem)

    def delete_problem(self, problem_id):
        return self._request("DELETE", f"/api/problems/{problem_id}")

    def set_log_visibility(self, problem_id, public_cases):
        return self._request("PUT", f"/api/problems/{problem_id}/log_visibility", json={"public_cases": public_cases})

    # ---- 语言 ----
    def list_languages(self):
        return self._request("GET", "/api/languages/")

    # ---- 提交 / 评测 ----
    def submit(self, problem_id, language, code):
        return self._request(
            "POST", "/api/submissions/",
            json={"problem_id": problem_id, "language": language, "code": code},
        )

    def get_submission(self, submission_id):
        return self._request("GET", f"/api/submissions/{submission_id}")

    def list_submissions(self, params: dict):
        return self._request("GET", "/api/submissions/", params=params)

    def get_log(self, submission_id):
        return self._request("GET", f"/api/submissions/{submission_id}/log")

    def rejudge(self, submission_id):
        return self._request("PUT", f"/api/submissions/{submission_id}/rejudge")

    # ---- AI 智能命题 ----
    def ai_set_config(self, cfg: dict):
        return self._request("PUT", "/api/ai/model-config", json=cfg)

    def ai_get_config(self):
        return self._request("GET", "/api/ai/model-config")

    def ai_create_task(self, requirement, problem_id=None, inplace=False):
        return self._request(
            "POST", "/api/ai/problem-tasks/",
            json={"requirement": requirement, "problem_id": problem_id, "inplace": inplace},
        )

    def ai_get_task(self, task_id):
        return self._request("GET", f"/api/ai/problem-tasks/{task_id}")

    def ai_cancel_task(self, task_id):
        return self._request("PUT", f"/api/ai/problem-tasks/{task_id}/cancel")
