"""题目业务逻辑。"""
from app import config, storage


def problem_to_public(p: dict) -> dict:
    """将内部存储的题目转换为接口返回结构，缺省可选字段返回默认值。"""
    return {
        "id": p.get("id", ""),
        "title": p.get("title", ""),
        "description": p.get("description", ""),
        "input_description": p.get("input_description", ""),
        "output_description": p.get("output_description", ""),
        "samples": p.get("samples", []),
        "constraints": p.get("constraints", ""),
        "testcases": p.get("testcases", []),
        "hint": p.get("hint", ""),
        "source": p.get("source", ""),
        "tags": p.get("tags", []),
        "time_limit": p.get("time_limit") if p.get("time_limit") is not None else config.DEFAULT_TIME_LIMIT,
        "memory_limit": p.get("memory_limit") if p.get("memory_limit") is not None else config.DEFAULT_MEMORY_LIMIT,
        "author": p.get("author", ""),
        "difficulty": p.get("difficulty", ""),
    }


async def delete_problem_cascade(problem_id: str):
    """删除题目并级联删除其测试点（内嵌）、相关提交（含 judge 日志）与访问审计。"""
    await storage.db.problems.delete(problem_id)

    # 相关提交（judge 日志 details 内嵌于提交中，随提交一并删除）
    for sid in list(storage.db.submissions.data.keys()):
        sub = storage.db.submissions.data.get(sid)
        if sub and sub.get("problem_id") == problem_id:
            await storage.db.submissions.delete(sid)

    await storage.db.access_log.remove_by_problem(problem_id)
