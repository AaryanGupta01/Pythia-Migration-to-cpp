"""FastAPI app: REST + WebSocket transport for the PYTHIA Studio engine (CONTRACTS section 6)."""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import playground
from .bus import Bus

log = logging.getLogger("pythia.studio")
ROOT = Path(__file__).resolve().parents[3]
DIST = ROOT / "studio" / "web" / "dist"
MAX_UPLOAD = 64 << 20
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", "testserver"}
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"]


def default_home() -> Path:
    return Path(os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio").expanduser()


def make_engine(home: Path, which: Optional[str] = None):
    """PYTHIA_ENGINE=mock|real (default real; falls back to mock with a loud log line)."""
    which = (which or os.environ.get("PYTHIA_ENGINE") or "real").lower()
    if which != "mock":
        try:
            from pythia.studio.engine import Engine
            return Engine(str(home))
        except Exception as e:
            banner = "!" * 78
            msg = (f"\n{banner}\n!! PYTHIA_ENGINE=real requested but pythia.studio.engine failed to import/start:\n"
                   f"!!   {type(e).__name__}: {e}\n!! FALLING BACK TO THE MOCK ENGINE: all data below is scripted demo data.\n{banner}\n")
            print(msg, file=sys.stderr)
            log.error("falling back to mock engine: %s", e)
    from .mock_engine import MockEngine
    return MockEngine(str(home))


def fs_list(path: str) -> dict:
    """Read-only directory listing for the folder picker."""
    p = Path(path).expanduser() if path else Path.home()
    try:
        p = p.resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise FileNotFoundError(f"no such folder: {path}")
    if not p.is_dir():
        raise NotADirectoryError(f"not a folder: {p}")
    entries = []
    try:
        for e in os.scandir(p):
            try:
                entries.append({"name": e.name, "type": "dir" if e.is_dir() else "file"})
            except OSError:
                continue
            if len(entries) >= 5000:
                break
    except PermissionError:
        raise PermissionError(f"permission denied: {p}")
    entries.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
    parent = str(p.parent) if p.parent != p else None
    return {"path": str(p), "parent": parent, "entries": entries, "home": str(Path.home())}


class LocalOnly:
    """Pure ASGI guard: only answer requests addressed to localhost (blocks DNS rebinding)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            host = dict(scope.get("headers") or []).get(b"host", b"").decode("latin1")
            name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
            if name and name.lower() not in LOCAL_HOSTS:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await JSONResponse({"error": "this server only answers requests addressed to localhost"}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _safe_rel(rel: str) -> str:
    if not rel or rel.startswith(("/", "\\")) or ".." in rel.replace("\\", "/").split("/") or ":" in rel:
        raise ValueError(f"invalid relative path '{rel}'")
    return rel


def create_app(engine=None, home: Optional[str] = None) -> FastAPI:
    home_p = Path(home) if home else default_home()
    home_p.mkdir(parents=True, exist_ok=True)
    engine = engine or make_engine(home_p)
    # an engine that writes jobs/<id>/events.jsonl itself (it exposes .events) stays the single writer
    bus = Bus(home_p, persist=not hasattr(engine, "events"))
    app = FastAPI(title="PYTHIA Studio", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.engine, app.state.bus, app.state.home = engine, bus, home_p
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(LocalOnly)

    # -- errors: always {"error": "..."} ---------------------------------------------------------
    def err(status: int, msg: str) -> JSONResponse:
        return JSONResponse({"error": msg}, status_code=status)

    @app.exception_handler(HTTPException)
    async def _http(_r, e: HTTPException):
        return err(e.status_code, str(e.detail))

    @app.exception_handler(RequestValidationError)
    async def _val(_r, e: RequestValidationError):
        first = e.errors()[0] if e.errors() else {}
        return err(422, f"invalid request: {'.'.join(str(x) for x in first.get('loc', []))}: {first.get('msg', 'bad value')}")

    @app.exception_handler(playground.PlaygroundError)
    async def _pg(_r, e):
        return err(e.status, str(e))

    for exc, status in ((KeyError, 404), (FileNotFoundError, 404), (NotADirectoryError, 400), (PermissionError, 403),
                        (ValueError, 400)):
        def make(status=status):
            async def h(_r, e):
                msg = e.args[0] if e.args else str(e)
                return err(status, str(msg))
            return h
        app.add_exception_handler(exc, make())

    @app.exception_handler(Exception)
    async def _any(_r, e):
        log.exception("unhandled error")
        return err(500, f"{type(e).__name__}: {e}")

    async def body(request: Request) -> dict:
        try:
            data = await request.json()
        except Exception:
            raise HTTPException(400, "request body must be JSON")
        if not isinstance(data, dict):
            raise HTTPException(400, "request body must be a JSON object")
        return data

    def need_job(job: str) -> str:
        engine.job(job)               # KeyError -> 404
        return job

    # -- env / settings --------------------------------------------------------------------------
    @app.get("/api/env")
    def env():
        return engine.env()

    @app.get("/api/settings")
    def get_settings():
        return engine.settings()

    @app.put("/api/settings")
    async def put_settings(request: Request):
        return engine.update_settings(await body(request))

    # -- jobs ------------------------------------------------------------------------------------
    def start(input_: dict, options: dict) -> dict:
        if not isinstance(input_, dict) or "kind" not in input_:
            raise HTTPException(422, "body needs input.kind (snippet|file|folder|git|demo)")
        if not isinstance(options, dict):
            raise HTTPException(422, "options must be an object")
        ch = bus.new_channel()
        job_id = engine.start_job(input_, options, ch.emit)
        ch.bind(job_id)
        bus.register(ch)
        ws = (engine.job(job_id) or {}).get("workspace_id")
        if not ws:
            ev = ch.find("job.start")
            ws = (ev or {}).get("data", {}).get("workspace_id")
        return {"job_id": job_id, "workspace_id": ws}

    @app.post("/api/jobs")
    async def post_jobs(request: Request):
        b = await body(request)
        return await asyncio.to_thread(start, b.get("input"), b.get("options") or {})

    @app.post("/api/upload")
    async def upload(request: Request):
        ctype = request.headers.get("content-type", "")
        if not ctype.startswith("multipart/form-data"):
            raise HTTPException(400, "send multipart/form-data with a 'file' field")
        raw = await request.body()
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, f"upload larger than {MAX_UPLOAD >> 20} MB")
        msg = BytesParser(policy=policy.HTTP).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + raw)
        fname = content = opts = None
        for part in msg.iter_parts():
            n = part.get_param("name", header="content-disposition")
            if part.get_filename() and fname is None:
                fname, content = os.path.basename(part.get_filename()), part.get_payload(decode=True)
            elif n == "options":
                import json
                opts = json.loads(part.get_content())
        if fname is None:
            raise HTTPException(400, "no file part in the upload")
        inp = {"kind": "file", "filename": fname, "content_b64": base64.b64encode(content or b"").decode()}
        return await asyncio.to_thread(start, inp, opts or {})

    @app.get("/api/jobs")
    def list_jobs():
        return engine.jobs()

    @app.get("/api/jobs/{job}")
    def get_job(job: str):
        return engine.job(job)

    def channel(job: str):
        ch = bus.channel(job)
        if ch is None:
            raise KeyError(f"unknown job '{job}'")
        return ch

    @app.get("/api/jobs/{job}/events")
    def events(job: str, after: int = 0):
        ch = channel(job)
        evs = ch.events(after)
        return {"events": evs, "last_seq": ch.last_seq()}

    @app.websocket("/api/jobs/{job}/ws")
    async def ws_events(ws: WebSocket, job: str, after: int = 0):
        await ws.accept()
        ch = bus.channel(job)
        if ch is None:
            await ws.send_json({"error": f"unknown job '{job}'"})
            await ws.close(code=4404)
            return
        q, backlog, finished = ch.subscribe(asyncio.get_running_loop(), after)
        last = after
        try:
            done = finished          # job.done already behind us: replay the tail and close
            for ev in backlog:
                await ws.send_json(ev)
                last = ev["seq"]
                done = done or ev["type"] == "job.done"
            # close once job.done was delivered; a log reloaded from disk (not live) ends with its backlog
            while not done and ch.live:
                ev = await q.get()
                if ev["seq"] <= last:
                    continue
                await ws.send_json(ev)
                last = ev["seq"]
                done = ev["type"] == "job.done"
        except (WebSocketDisconnect, RuntimeError):
            return
        finally:
            ch.unsubscribe(q)
        try:
            await ws.close()
        except Exception:
            pass

    @app.post("/api/jobs/{job}/cancel")
    def cancel(job: str):
        need_job(job)
        engine.cancel(job)
        return {"ok": True}

    @app.get("/api/jobs/{job}/functions")
    def functions(job: str):
        return engine.functions(need_job(job))

    @app.get("/api/jobs/{job}/function")
    def function(job: str, id: str, stages: int = 0):
        return engine.function(need_job(job), id, stages=bool(stages))

    @app.post("/api/jobs/{job}/decision")
    async def decision(job: str, request: Request):
        b = await body(request)
        if b.get("decision") not in ("accepted", "rejected", "pending"):
            raise HTTPException(422, "decision must be accepted, rejected or pending")
        if not isinstance(b.get("id"), str):
            raise HTTPException(422, "id must be a function id or 'all'")
        r = engine.decide(need_job(job), b["id"], b["decision"])
        return r if isinstance(r, dict) else {"functions": r}

    @app.get("/api/jobs/{job}/file-diff")
    def file_diff(job: str, path: str):
        return engine.file_diff(need_job(job), _safe_rel(path))

    @app.post("/api/jobs/{job}/export")
    async def export(job: str, request: Request):
        b = await body(request) if (await request.body()) else {}
        return {"path": str(await asyncio.to_thread(engine.export, need_job(job), b.get("dest"), bool(b.get("zip"))))}

    @app.get("/api/jobs/{job}/export.zip")
    def export_zip(job: str):
        p = Path(engine.export(need_job(job), None, True))
        return FileResponse(p, media_type="application/zip", filename=p.name)

    @app.get("/api/jobs/{job}/report")
    def report(job: str):
        return engine.report(need_job(job))

    # -- workspaces / fs -------------------------------------------------------------------------
    @app.get("/api/workspaces/recent")
    def recent():
        return engine.recent()

    @app.get("/api/workspaces/{ws}/tree")
    def tree(ws: str):
        return engine.tree(ws)

    @app.get("/api/workspaces/{ws}/file")
    def read_file(ws: str, path: str, version: str = "work"):
        if version not in ("work", "original"):
            raise HTTPException(422, "version must be work or original")
        return engine.read_file(ws, _safe_rel(path), version)

    @app.get("/api/fs/list")
    def fs(path: str = ""):
        fn = getattr(engine, "list_dir", None)
        return fn(path) if fn else fs_list(path)

    # -- playground ------------------------------------------------------------------------------
    async def source_of(request: Request) -> str:
        b = await body(request)
        return b.get("source")

    @app.post("/api/playground/compile")
    async def pg_compile(request: Request):
        return await asyncio.to_thread(playground.compile_snippet, await source_of(request))

    @app.post("/api/playground/run")
    async def pg_run(request: Request):
        return await asyncio.to_thread(playground.run_snippet, await source_of(request), home_p / "build-cache")

    @app.post("/api/stages")
    async def pg_stages(request: Request):
        return await asyncio.to_thread(playground.stages, await source_of(request))

    @app.on_event("shutdown")
    def _shutdown():
        bus.close()

    # -- static UI ---------------------------------------------------------------------------------
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/") or path == "api":
            return err(404, f"no such endpoint: /{path}")
        if DIST.is_dir():
            f = (DIST / path).resolve()
            if path and f.is_file() and DIST.resolve() in f.parents:
                return FileResponse(f)
            return FileResponse(DIST / "index.html")
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>PYTHIA Studio</title>"
            "<body style='font:16px system-ui;background:#0b0c0e;color:#d8dade;padding:48px;max-width:640px'>"
            "<h1 style='font-weight:600'>PYTHIA Studio API is running</h1>"
            "<p>The web UI has not been built yet (<code>studio/web/dist</code> is missing).</p>"
            "<p>Build it with <code>cd studio/web &amp;&amp; npm install &amp;&amp; npm run build</code>, "
            "or browse the API at <a style='color:#8ab4ff' href='/api/docs'>/api/docs</a>.</p>")

    return app
