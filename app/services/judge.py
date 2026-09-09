"""评测引擎。

- 异步：评测作为后台 asyncio 任务执行，编译/运行的阻塞子进程通过
  ``asyncio.to_thread`` 移出事件循环（API 层仍为 async def，事件循环不阻塞）；
- 资源限制：时间用 ``subprocess`` 的 timeout，内存用 psutil 后台线程轮询 RSS；
- 判题结果：AC/WA/TLE/MLE/RE/CE/UNK；提交状态：pending/success/error。
"""
import asyncio
import os
import shlex
import shutil
import subprocess
import threading
import time
import uuid

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
    # POSIX 语义下双引号内的反斜杠按字面量保留、引号被剥离；
    # {src}/{exe} 占位符在拆分后再填充，因此路径中的反斜杠不会经过 shlex。
    tokens = shlex.split(template)
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


def _run_case_sync(run_cmd: list, input_bytes: bytes, time_limit: float, memory_limit: float, workdir: str):
    proc = subprocess.Popen(
        run_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
        stdout_b, stderr_b = proc.communicate(input_bytes, timeout=time_limit)
        elapsed = time.perf_counter() - start
        if mle_flag[0]:
            result = "MLE"
        elif proc.returncode != 0:
            result = "RE"
    except subprocess.TimeoutExpired:
        elapsed = time_limit
        try:
            proc.kill()
        except Exception:
            pass
        try:
            stdout_b, stderr_b = proc.communicate()
        except Exception:
            pass
        result = "TLE"
    finally:
        stop_event.set()
        monitor.join(timeout=1.0)

    return result, elapsed, peak[0], stdout_b, stderr_b


def _compile_sync(compile_cmd: list, workdir: str):
    try:
        proc = subprocess.run(
            compile_cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
            timeout=config.COMPILE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, "compile timeout"
    except FileNotFoundError:
        # 编译器不存在（如未安装 g++）：作为编译失败返回，避免向上抛 WinError
        return False, f"compiler not found: {compile_cmd[0]}"
    except OSError as e:
        return False, f"compile failed: {e}"
    if proc.returncode != 0:
        msg = (proc.stderr + proc.stdout).decode("utf-8", errors="replace") or "compile error"
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

    os.makedirs(config.WORK_DIR, exist_ok=True)
    workdir = os.path.join(config.WORK_DIR, f"oj_{uuid.uuid4().hex}")
    os.makedirs(workdir, exist_ok=True)
    try:
        src_name = "main" + (lang.get("file_ext") or "")
        src_path = os.path.join(workdir, src_name)
        exe_path = os.path.join(workdir, "main.exe" if os.name == "nt" else "main")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(sub.get("code", ""))

        compile_info = {"result": "success", "message": ""}
        if lang.get("compile_cmd"):
            compile_cmd = _fill_cmd(lang["compile_cmd"], src_path, exe_path)
            ok_compile, cmsg = await asyncio.to_thread(_compile_sync, compile_cmd, workdir)
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
            result, elapsed, mem, stdout_b, stderr_b = await asyncio.to_thread(
                _run_case_sync, run_cmd, inp, float(tl), float(ml), workdir
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
