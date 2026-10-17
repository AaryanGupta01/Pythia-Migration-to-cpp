"""Ingest: snippet | file | folder | git | demo  ->  Workspace (original/ and work/ identical copies).

The user's source is only ever read. Project contents are copied to the workspace ROOT
(no extra top-level folder), so relpaths in function ids are project-relative.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import pathspec

from .models import Workspace

SKIP_DIRS = {"venv", ".venv", "node_modules", ".git", "__pycache__", "build", "dist",
             ".tox", ".mypy_cache", ".pytest_cache", ".idea", ".vscode", ".ruff_cache",
             "site-packages", ".eggs"}
SKIP_SUFFIX = (".pyc", ".pyo")
MAX_FILE_BYTES = 5 * 1024 * 1024
GIT_TIMEOUT_S = 300
REPO_ROOT = Path(__file__).resolve().parents[2]
from ..paths import DEMO  # noqa: E402  (wheel or checkout)


def _noop(*_a, **_k):
    pass


def _safe_name(name: str, default: str) -> str:
    n = re.sub(r"[^A-Za-z0-9_.-]+", "_", (name or "").strip()).strip("._")
    return n or default


def _load_spec(d: Path):
    gi = d / ".gitignore"
    if gi.is_file():
        try:
            return pathspec.GitIgnoreSpec.from_lines(gi.read_text(encoding="utf-8", errors="replace").splitlines())
        except Exception:
            return None
    return None


class _Copier:
    def __init__(self, dst: Path, emit: Callable):
        self.dst, self.emit = dst, emit
        self.files = 0
        self.bytes = 0
        self.skipped: List[Dict[str, str]] = []

    def skip(self, rel: str, reason: str):
        self.skipped.append({"path": rel, "reason": reason})

    def copy_tree(self, src: Path):
        # stack of (base_dir, spec) so nested .gitignore files apply to their own subtree
        self._walk(src, src, [])

    def _ignored(self, p: Path, is_dir: bool, specs) -> bool:
        for base, spec in specs:
            rel = p.relative_to(base).as_posix() + ("/" if is_dir else "")
            if spec.match_file(rel):
                return True
        return False

    def _walk(self, root: Path, d: Path, specs):
        spec = _load_spec(d)
        if spec is not None:
            specs = specs + [(d, spec)]
        try:
            entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError as e:
            self.skip(d.relative_to(root).as_posix() or ".", f"unreadable directory ({e.strerror})")
            return
        for e in entries:
            p = Path(e.path)
            rel = p.relative_to(root).as_posix()
            try:
                if e.is_symlink():
                    self.skip(rel, "symlink")
                    continue
                if e.is_dir(follow_symlinks=False):
                    if e.name in SKIP_DIRS or e.name.endswith(".egg-info"):
                        self.skip(rel + "/", "excluded directory")
                    elif self._ignored(p, True, specs):
                        self.skip(rel + "/", "matched .gitignore")
                    else:
                        self._walk(root, p, specs)
                    continue
                if e.name.endswith(SKIP_SUFFIX):
                    continue
                if self._ignored(p, False, specs):
                    self.skip(rel, "matched .gitignore")
                    continue
                size = e.stat(follow_symlinks=False).st_size
                if size > MAX_FILE_BYTES:
                    self.skip(rel, f"file larger than 5 MB ({size / 1048576:.1f} MB)")
                    continue
                out = self.dst / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(p, out)
                self.files += 1
                self.bytes += size
                if self.files % 25 == 0:
                    self._progress("copy", rel)
            except OSError as ex:
                self.skip(rel, f"could not copy ({ex.strerror})")

    def _progress(self, phase: str, current):
        self.emit("ingest.progress", {"phase": phase, "files": self.files, "bytes": self.bytes,
                                      "current": current,
                                      "message": f"Copied {self.files} files"}, stage="ingest")


def _git_clone(url: str, dest: Path, emit) -> None:
    if not shutil.which("git"):
        raise RuntimeError("git is not installed or not on PATH; install it to clone repositories")
    src = url.strip()
    if Path(src).exists():                       # local bare repo / working repo: use file:// so --depth works
        src = Path(src).resolve().as_uri()
    emit("ingest.progress", {"phase": "clone", "files": 0, "bytes": 0, "current": url,
                             "message": f"Cloning {url} (depth 1)"}, stage="ingest")
    try:
        r = subprocess.run(["git", "clone", "--depth", "1", "--quiet", src, str(dest)],
                           capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git clone timed out after {GIT_TIMEOUT_S}s")
    if r.returncode != 0:
        raise RuntimeError("git clone failed: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1])


def _write_snippet(inp: dict, original: Path) -> str:
    name = _safe_name(inp.get("name", ""), "snippet")
    fname = name if name.endswith(".py") else name + ".py"
    (original / fname).write_text(inp.get("code", ""), encoding="utf-8", newline="\n")
    return name[:-3] if name.endswith(".py") else name


def ingest(input: dict, home, emit=None) -> Workspace:
    emit = emit or _noop
    home = Path(home)
    kind = input.get("kind", "")
    ws_id = input.get("ws_id") or uuid.uuid4().hex[:8]     # B2: Engine preallocates the workspace id
    root = home / "workspaces" / ws_id
    original, work = root / "original", root / "work"
    original.mkdir(parents=True, exist_ok=True)
    cp = _Copier(original, emit)
    origin = ""
    tmp_clone = None
    try:
        if kind == "snippet":
            name = _write_snippet(input, original)
            cp.files, cp.bytes, origin = 1, len(input.get("code", "").encode()), "snippet"
            emit("ingest.progress", {"phase": "copy", "files": 1, "bytes": cp.bytes,
                                     "current": name + ".py", "message": "Wrote snippet"}, stage="ingest")
        elif kind == "file":
            fname = _safe_name(os.path.basename(input.get("filename") or input.get("path") or ""), "upload.py")
            if input.get("content_b64") is not None:
                data = base64.b64decode(input["content_b64"])
            elif input.get("path"):
                data = Path(input["path"]).read_bytes()
                origin = str(input["path"])
            else:
                raise ValueError("file input needs content_b64 or path")
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("file larger than 5 MB")
            (original / fname).write_bytes(data)
            cp.files, cp.bytes, origin = 1, len(data), origin or fname
            name = fname[:-3] if fname.endswith(".py") else fname
            emit("ingest.progress", {"phase": "copy", "files": 1, "bytes": len(data),
                                     "current": fname, "message": f"Received {fname}"}, stage="ingest")
        elif kind in ("folder", "demo", "git"):
            if kind == "folder":
                src = Path(input.get("path", "")).expanduser()
                if not src.is_dir():
                    raise ValueError(f"folder not found: {src}")
                origin, name = str(src), src.resolve().name
            elif kind == "demo":
                from .demos import resolve
                entry = resolve(input.get("name"))
                src = entry["path"]
                if not src.is_dir():
                    raise ValueError(f"demo project not found at {src}")
                origin, name = "demo/" + entry["dir"], entry["name"]
            else:
                url = input.get("url", "").strip()
                if not url:
                    raise ValueError("git input needs a url")
                tmp_clone = root / "_clone"
                _git_clone(url, tmp_clone, emit)
                src, origin = tmp_clone, url
                name = re.sub(r"\.git$", "", url.rstrip("/").replace("\\", "/").split("/")[-1].split(":")[-1]) or "repo"
            emit("ingest.progress", {"phase": "copy", "files": 0, "bytes": 0, "current": str(src),
                                     "message": f"Copying {name}"}, stage="ingest")
            cp.copy_tree(src.resolve())
        else:
            raise ValueError(f"unknown input kind {kind!r}")
    finally:
        if tmp_clone is not None:
            shutil.rmtree(tmp_clone, ignore_errors=True)

    emit("ingest.progress", {"phase": "index", "files": cp.files, "bytes": cp.bytes, "current": None,
                             "message": "Indexing Python files"}, stage="ingest")
    py_files = sorted(p.relative_to(original).as_posix() for p in original.rglob("*.py") if p.is_file())
    shutil.copytree(original, work)              # work/ starts identical to original/
    ws = Workspace(ws_id=ws_id, name=name, root=root, original=original, work=work,
                   py_files=py_files, skipped=cp.skipped, input_kind=kind, origin=origin)
    (root / "workspace.json").write_text(json.dumps(ws.to_dict(), indent=1), encoding="utf-8")
    emit("ingest.done", {"workspace_id": ws_id, "name": name, "files": cp.files,
                         "py_files": len(py_files), "skipped": cp.skipped}, stage="ingest",
         caption=f"Ingested {name}: {len(py_files)} Python files")
    return ws
