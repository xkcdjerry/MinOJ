"""评测引擎。

- 异步：编译/运行使用 asyncio.create_subprocess_exec；
- 资源限制：时间用 asyncio.wait_for，内存用 psutil 后台线程轮询 RSS；
- 判题结果：AC/WA/TLE/MLE/RE/CE/UNK；提交状态：pending/success/error。
"""
import asyncio
import os
import shlex
import shutil
import tempfile
import threading
import time

import psutil

from app import config, storage
from app.services import user_service


def _normalize_output(s: str) -> str:
    """忽略每行行末空白与最后一行多余换行。"""
    text = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.rstrip("\n").split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _sanitize(msg: str, workdir: str) -> str:
    if not msg:
        return msg
    return msg.replace(workdir, "<workdir>")


def _fill_cmd(template: str, src: str, exe: str) -> list:
    # Windows 下 backslash 路径应视为字面量（posix=False），Linux 下保持 POSIX 语义
    tokens = shlex.split(template, posix=(os.name != "nt"))
    return [t.replace("{src}", src).replace("{exe}", exe) for t in tokens]


def _monitor_memory(pid: int, mem_limit_mb: float, stop_event: threading.Event, peak: list, mle_flag: list):
    try:
        proc = psutil.Process(pid)
        while not stop_event.is_set():
            try:
                rss = proc.memory_info().rss / (1024 ** 2)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            peak[0] = max(peak[0], rss)
            if rss > mem_limit_mb:
                mle_flag[0] = True
                try:
                    proc.kill()
                except Exception:
                    pass
                break
            time.sleep(0.05)
    except Exception:
        pass


async def _run_case(run_cmd: list, input_bytes: bytes, time_limit: float, memory_limit: float, workdir: str):
    proc = await asyncio.create_subprocess_exec(
        *run_cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
    )
    stop_event = threading.Event()
    peak = [0.0]
    mle_flag = [False]
    monitor = threading.Thread(
        target=_monitor_memory, args=(proc.pid, memory_limit, stop_event, peak, mle_flag), daemon=True
    )
    monitor.start()

    start = time.perf_counter()
    result = None
    stdout_b = b""
    stderr_b = b""
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(input_bytes), timeout=time_limit)
        elapsed = time.perf_counter() - start
        if mle_flag[0]:
            result = "MLE"
        elif proc.returncode != 0:
            result = "RE"
    except asyncio.TimeoutError:
        elapsed = time_limit
        try:
            proc.kill()
        except Exception:
            pass
        try:
            await proc.wait()
        except Exception:
            pass
        result = "TLE"
    finally:
        stop_event.set()
        monitor.join(timeout=1.0)

    return result, elapsed, peak[0], stdout_b, stderr_b


async def _compile(compile_cmd: list, workdir: str):
    proc = await asyncio.create_subprocess_exec(
        *compile_cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=config.COMPILE_TIMEOUT)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return False, "compile timeout"
    if proc.returncode != 0:
        msg = (stderr_b + stdout_b).decode("utf-8", errors="replace") or "compile error"
        return False, msg
    return True, ""


async def run_judge(submission_id: str):
    sub = await storage.db.submissions.get(submission_id)
    if sub is None:
        return
    problem = await storage.db.problems.get(sub.get("problem_id"))
    lang = await storage.db.languages.get(sub.get("language"))
    if problem is None or lang is None:
        sub["status"] = "error"
        sub["error_info"] = "problem or language not found"
        await _persist(submission_id, sub, update_stats=False)
        return

    testcases = problem.get("testcases", [])
    counts = len(testcases) * 10

    workdir = tempfile.mkdtemp(prefix="oj_")
    try:
        src_name = "main" + (lang.get("file_ext") or "")
        src_path = os.path.join(workdir, src_name)
        exe_path = os.path.join(workdir, "main.exe" if os.name == "nt" else "main")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(sub.get("code", ""))

        compile_info = {"result": "success", "message": ""}
        if lang.get("compile_cmd"):
            ok_compile, cmsg = await _compile(_fill_cmd(lang["compile_cmd"], src_path, exe_path), workdir)
            if not ok_compile:
                compile_info = {"result": "failed", "message": _sanitize(cmsg, workdir)[:2000]}
                details = [
                    {"id": i + 1, "result": "CE", "time": 0.0, "memory": 0}
                    for i in range(len(testcases))
                ]
                sub.update({
                    "status": "success",
                    "score": 0,
                    "counts": counts,
                    "compile_info": compile_info,
                    "run_info": {"result": "finished", "message": "compilation failed"},
                    "error_info": "",
                    "details": details,
                })
                await _persist(submission_id, sub)
                return

        run_cmd = _fill_cmd(lang["run_cmd"], src_path, exe_path)

        tl = problem.get("time_limit")
        if tl is None:
            tl = lang.get("time_limit")
            if tl is None:
                tl = config.DEFAULT_TIME_LIMIT
        ml = problem.get("memory_limit")
        if ml is None:
            ml = lang.get("memory_limit")
            if ml is None:
                ml = config.DEFAULT_MEMORY_LIMIT

        details = []
        score = 0
        for i, tc in enumerate(testcases):
            inp = (tc.get("input", "") + "\n").encode("utf-8")
            result, elapsed, mem, stdout_b, stderr_b = await _run_case(
                run_cmd, inp, float(tl), float(ml), workdir
            )
            if result is None:
                result = (
                    "AC"
                    if _normalize_output(stdout_b.decode("utf-8", errors="replace"))
                    == _normalize_output(tc.get("output", ""))
                    else "WA"
                )
            if result == "AC":
                score += 10
            details.append({"id": i + 1, "result": result, "time": round(elapsed, 3), "memory": int(mem)})

        sub.update({
            "status": "success",
            "score": score,
            "counts": counts,
            "compile_info": compile_info,
            "run_info": {"result": "finished", "message": f"{len(testcases)} test cases finished"},
            "error_info": "",
            "details": details,
        })
        await _persist(submission_id, sub)
    except Exception as e:  # noqa: BLE001 - 评测自身异常
        sub["status"] = "error"
        sub["error_info"] = str(e)[:2000]
        await _persist(submission_id, sub, update_stats=False)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def _persist(submission_id: str, sub: dict, update_stats: bool = True):
    """写回提交；若提交已被删除（如题目级联删除），则不复活它。"""
    if await storage.db.submissions.get(submission_id) is None:
        return
    await storage.db.submissions.put(submission_id, sub)
    if update_stats:
        await _update_user_stats(sub)


async def _update_user_stats(sub: dict):
    user = await storage.db.users.get(sub.get("user_id"))
    if user is None:
        return
    solved = set(user.get("solved_problems", []))
    if sub.get("status") == "success" and sub.get("counts") and sub.get("score") == sub.get("counts"):
        solved.add(sub.get("problem_id"))
    user["solved_problems"] = list(solved)
    user["resolve_count"] = len(solved)
    await storage.db.users.put(sub.get("user_id"), user)
