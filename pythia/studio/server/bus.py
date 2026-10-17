"""Event bus: assigns seq/ts, persists to jobs/<job_id>/events.jsonl, fans out to WebSocket subscribers.

Thread-safe: the engine emits from background threads; subscribers are asyncio queues that are
fed with `loop.call_soon_threadsafe`. `Channel.subscribe` snapshots the backlog and registers the
queue under the same lock that `emit` uses, so a subscriber sees every event exactly once.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Channel:
    def __init__(self, home: Path, job_id: Optional[str] = None, live: bool = True, persist: bool = True):
        self._home = home
        self._persist = persist       # False when the engine already writes events.jsonl itself (same seq numbering)
        self._lock = threading.Lock()
        self._events: List[dict] = []
        self._subs: List[Tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []
        self._fh = None
        self.job_id = job_id
        self.live = live              # False for logs reloaded from disk: nothing more will arrive
        self.finished = False         # job.done seen
        if job_id and persist:
            self._open()

    # -- persistence -----------------------------------------------------------------------
    def _open(self) -> None:
        d = self._home / "jobs" / self.job_id
        d.mkdir(parents=True, exist_ok=True)
        self._fh = open(d / "events.jsonl", "a", encoding="utf-8", newline="\n")

    def bind(self, job_id: str) -> None:
        """Attach to a job id once the engine returned it; flushes events emitted before that."""
        with self._lock:
            self.job_id = job_id
            if self._persist:
                self._open()
                for ev in self._events:
                    self._fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
                self._fh.flush()

    @staticmethod
    def from_disk(home: Path, job_id: str) -> Optional["Channel"]:
        p = home / "jobs" / job_id / "events.jsonl"
        if not p.is_file():
            return None
        ch = Channel(home, None, live=False)
        ch.job_id = job_id
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                ch._events.append(json.loads(line))
            except ValueError:
                continue                      # truncated last line after a crash
        ch.finished = any(e.get("type") == "job.done" for e in ch._events)
        return ch

    # -- producer side ---------------------------------------------------------------------
    def emit(self, type: str, data: Optional[dict] = None, stage: Optional[str] = None, caption: Optional[str] = None) -> dict:
        with self._lock:
            ev = {"seq": len(self._events) + 1, "ts": round(time.time(), 3), "type": type, "stage": stage,
                  "caption": caption, "data": data if data is not None else {}}
            self._events.append(ev)
            if self._fh:
                self._fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
                self._fh.flush()
            if type == "job.done":
                self.finished = True
            for loop, q in list(self._subs):
                try:
                    loop.call_soon_threadsafe(q.put_nowait, ev)
                except RuntimeError:          # loop closed
                    self._subs.remove((loop, q))
        return ev

    # -- consumer side ---------------------------------------------------------------------
    def events(self, after: int = 0) -> List[dict]:
        with self._lock:
            return self._events[max(0, after):]          # seq n lives at index n-1

    def last_seq(self) -> int:
        with self._lock:
            return len(self._events)

    def subscribe(self, loop: asyncio.AbstractEventLoop, after: int = 0) -> Tuple[asyncio.Queue, List[dict], bool]:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            backlog = self._events[max(0, after):]
            finished = self.finished
            if self.live:
                self._subs.append((loop, q))
        return q, backlog, finished

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs = [(l, x) for (l, x) in self._subs if x is not q]

    def find(self, type: str) -> Optional[dict]:
        with self._lock:
            return next((e for e in self._events if e["type"] == type), None)

    def close(self) -> None:
        with self._lock:
            if self._fh:
                self._fh.close()
                self._fh = None


class Bus:
    def __init__(self, home: Path, persist: bool = True):
        self.home = Path(home)
        self.persist = persist
        self._chans: Dict[str, Channel] = {}
        self._lock = threading.Lock()

    def new_channel(self) -> Channel:
        return Channel(self.home, persist=self.persist)

    def register(self, ch: Channel) -> None:
        with self._lock:
            self._chans[ch.job_id] = ch

    def channel(self, job_id: str) -> Optional[Channel]:
        if not job_id or "/" in job_id or "\\" in job_id or job_id.startswith("."):
            return None
        with self._lock:
            ch = self._chans.get(job_id)
            if ch is None:
                ch = Channel.from_disk(self.home, job_id)
                if ch is not None:
                    self._chans[job_id] = ch
            return ch

    def close(self) -> None:
        with self._lock:
            for ch in self._chans.values():
                ch.close()
