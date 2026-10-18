"""Small subprocess helpers shared by trace / replay / bench: process-group
spawn, streaming tail, clean kill."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

IS_WIN = os.name == "nt"


def make_bin_dir(d: Path) -> Path:
    """`python`/`python3` wrappers that exec THIS interpreter (keeps the venv)."""
    b = d / "bin"
    b.mkdir(parents=True, exist_ok=True)
    for n in ("python", "python3"):
        if IS_WIN:                                   # cmd.exe finds .bat through PATHEXT, ahead of python.exe
            (b / f"{n}.bat").write_text(f'@"{sys.executable}" %*\r\n', encoding="utf-8")
            continue
        p = b / n
        p.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
        try:
            p.chmod(0o755)
        except OSError:
            pass
    return b


def _kill_tree_win(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=15,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def kill_group(p: subprocess.Popen, grace: float = 3.0) -> None:
    if p.poll() is not None:
        return
    if IS_WIN:
        _kill_tree_win(p.pid)
        try:
            p.wait(timeout=5)
        except Exception:
            pass
        return
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        else:
            p.terminate()
        p.wait(timeout=grace)
    except Exception:
        pass
    if p.poll() is None:
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            else:
                p.kill()
        except Exception:
            pass
        try:
            p.wait(timeout=5)
        except Exception:
            pass


class Run:
    """Result of run_cmd."""
    def __init__(self):
        self.exit_code: Optional[int] = None
        self.timed_out = False
        self.cancelled = False
        self.elapsed = 0.0
        self.output = b""


def run_cmd(cmd: str, cwd: Path, env: Dict[str, str], timeout_s: float,
            on_tick: Optional[Callable[[float, str], None]] = None,
            cancelled: Optional[Callable[[], bool]] = None, tick_s: float = 0.4,
            tail_chars: int = 4000, max_keep: int = 4_000_000) -> Run:
    """Run `cmd` (shell if it has shell syntax) in its own process group; merge
    stderr into stdout; hard timeout; `on_tick(elapsed, tail)` roughly every tick_s."""
    import shlex
    shell = IS_WIN or any(c in cmd for c in "&|;<>$`()")   # Windows: cmd.exe resolves the python.bat shim
    argv = cmd if shell else shlex.split(cmd)
    r = Run()
    t0 = time.perf_counter()
    p = subprocess.Popen(argv, cwd=str(cwd), env=env, shell=shell, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         start_new_session=hasattr(os, "setsid"),
                         creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0))
                         if IS_WIN else 0)
    chunks: List[bytes] = []
    kept = [0]
    tail = [b""]

    def pump():
        for chunk in iter(lambda: p.stdout.read1(65536) if hasattr(p.stdout, "read1") else p.stdout.read(65536), b""):
            if kept[0] < max_keep:
                chunks.append(chunk)
                kept[0] += len(chunk)
            tail[0] = (tail[0] + chunk)[-tail_chars * 2:]

    th = threading.Thread(target=pump, daemon=True)
    th.start()
    last = 0.0
    while p.poll() is None:
        now = time.perf_counter() - t0
        if now > timeout_s:
            r.timed_out = True
            kill_group(p)
            break
        if cancelled and cancelled():
            r.cancelled = True
            kill_group(p)
            break
        if on_tick and now - last >= tick_s:
            last = now
            on_tick(now, tail[0][-tail_chars:].decode("utf-8", "replace"))
        time.sleep(0.05)
    r.elapsed = time.perf_counter() - t0
    if p.poll() is None:
        kill_group(p)
    r.exit_code = p.returncode
    th.join(timeout=2)
    # a grandchild may still hold the pipe: make sure the whole group is gone
    if hasattr(os, "killpg"):
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass
    r.output = b"".join(chunks)
    return r
