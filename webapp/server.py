"""
FastAPI backend for the WE Automation Tools web launcher.

It exposes the existing desktop tools over HTTP + WebSocket so that a plain
HTML/CSS/JS front-end can drive them from a browser.

Key responsibilities
--------------------
*   Serve the static front-end (index.html / style.css / app.js).
*   Report the tool registry and their dependency status.
*   Start / stop a tool. Each running tool gets an id and emits log lines
    that are pushed to the browser over a WebSocket.

Run it with:
    python -m uvicorn webapp.server:app --reload --port 8000
or simply:
    python webapp/server.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .tools import BASE_DIR, PACKAGE_ALTERNATIVES, TOOLS, get_tool
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="WE Automation Tools", version="1.0.0")


@app.middleware("http")
async def no_browser_cache(request, call_next):
    """Always serve the local development/enterprise UI fresh.

    This removes the need for Ctrl+Shift+R after every UI update, while the
    API remains cache-safe as well.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ECRM has a full web UI of its own (not just a launcher card), so it ships
# its own router with meta/upload/run/stop/history endpoints.
from .ecrm_routes import router as ecrm_router  # noqa: E402
app.include_router(ecrm_router)


# ---------------------------------------------------------------------------
# Dependency checking
# ---------------------------------------------------------------------------
def _module_available(package: str) -> bool:
    """Return True if ``package`` (or one of its import aliases) is importable."""
    candidates = PACKAGE_ALTERNATIVES.get(package.lower(), [package, package.lower()])
    for name in candidates:
        try:
            importlib.import_module(name)
            return True
        except ImportError:
            continue
    return False


def check_dependencies(requires: List[str]) -> tuple[bool, List[str]]:
    missing = [pkg for pkg in requires if not _module_available(pkg)]
    return (len(missing) == 0), missing


# ---------------------------------------------------------------------------
# Running-job registry
# ---------------------------------------------------------------------------
@dataclass
class Job:
    id: str
    tool_id: str
    tool_name: str
    mode: Optional[str] = None
    status: str = "running"          # running | done | error | stopped
    return_code: Optional[int] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None
    output_file: str = ""
    records_total: int = 0
    progress: float = 0.0
    input_files: int = 0
    captcha_image: str = ""
    captcha_event: object = field(default_factory=threading.Event)
    captcha_value: str = ""
    lines: List[dict] = field(default_factory=list)   # replay buffer for late subscribers
    process: Optional[subprocess.Popen] = None
    thread: Optional[threading.Thread] = None

    def append(self, message: str, level: str = "info") -> dict:
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "level": level,
        }
        self.lines.append(entry)
        return entry


JOBS: Dict[str, Job] = {}
JOBS_LOCK = threading.Lock()
JOB_STORE = BASE_DIR / "webapp" / "jobs.json"
PERSISTED_JOBS: Dict[str, dict] = {}

def _load_job_store():
    global PERSISTED_JOBS
    try:
        if JOB_STORE.exists():
            PERSISTED_JOBS = json.loads(JOB_STORE.read_text(encoding="utf-8"))
    except Exception:
        PERSISTED_JOBS = {}

def _save_job_meta(job: Job):
    try:
        JOB_STORE.parent.mkdir(parents=True, exist_ok=True)
        PERSISTED_JOBS[job.id] = {"job_id":job.id,"tool_id":job.tool_id,"tool":job.tool_name,"mode":job.mode,"status":job.status,"started_at":job.started_at,"finished_at":job.finished_at,"output_file":job.output_file,"records":job.records_total,"progress":job.progress,"input_files":job.input_files}
        # keep the metadata store bounded
        items=sorted(PERSISTED_JOBS.items(), key=lambda kv: kv[1].get("started_at", ""), reverse=True)[:500]
        PERSISTED_JOBS.clear(); PERSISTED_JOBS.update(items)
        JOB_STORE.write_text(json.dumps(PERSISTED_JOBS, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

_load_job_store()


def _classify(line: str) -> str:
    lowered = line.lower()
    if "error" in lowered or "❌" in line or "traceback" in lowered:
        return "error"
    if "warn" in lowered or "⚠" in line:
        return "warning"
    if "✅" in line or "success" in lowered or "done" in lowered:
        return "success"
    return "info"


# ---------------------------------------------------------------------------
# WebSocket hub: broadcast log lines to every subscribed browser
# ---------------------------------------------------------------------------
class LogHub:
    def __init__(self) -> None:
        self._clients: Dict[str, List[WebSocket]] = {}
        self._lock = threading.Lock()

    def register(self, job_id: str, ws: WebSocket) -> None:
        with self._lock:
            self._clients.setdefault(job_id, []).append(ws)

    def unregister(self, job_id: str, ws: WebSocket) -> None:
        with self._lock:
            clients = self._clients.get(job_id)
            if clients and ws in clients:
                clients.remove(ws)

    def broadcast(self, job_id: str, payload: dict) -> None:
        with self._lock:
            clients = list(self._clients.get(job_id, []))
        dead = []
        for ws in clients:
            try:
                # FastAPI/Starlette WebSocket send is not thread-safe; schedule
                # onto the event loop when possible.
                _send_threadsafe(ws, payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister(job_id, ws)


HUB = LogHub()


def _send_threadsafe(ws: WebSocket, payload: dict) -> None:
    """Send JSON to a websocket from a worker thread."""
    import asyncio

    loop = getattr(ws, "_loop", None) or getattr(ws, "loop", None)
    if loop is None:
        # Fallback: run the coroutine on the current running loop if present.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
    if loop is not None and loop.is_running():
        asyncio.run_coroutine_threadsafe(ws.send_json(payload), loop)
    else:
        # Last resort: best-effort direct send.
        asyncio.run(ws.send_json(payload))


# ---------------------------------------------------------------------------
# Job execution
# ---------------------------------------------------------------------------
def _emit(job: Job, message: str, level: Optional[str] = None) -> None:
    level = level or _classify(message)
    entry = job.append(str(message), level)
    HUB.broadcast(job.id, {"type": "log", **entry})


def _run_native(job: Job, tool) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        [sys.executable, str(tool.path)],
        cwd=str(tool.path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    job.process = proc
    assert proc.stdout is not None
    for raw in proc.stdout:
        if raw:
            _emit(job, raw.rstrip("\n"))
    proc.wait()
    job.return_code = proc.returncode


def _run_cli(job: Job, tool) -> None:
    """Load the script as a module and call its runner function in-process."""
    spec = importlib.util.spec_from_file_location(f"tool_{tool.id}", str(tool.path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {tool.path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    runner = getattr(module, tool.runner, None) if tool.runner else None
    if runner is None:
        raise RuntimeError(f"Runner '{tool.runner}' not found in {tool.path.name}")

    def log_callback(msg):
        _emit(job, msg)

    # ``wo_unified.run_wo_unified`` accepts ``mode`` and ``log``; other runners
    # may accept only ``log`` or nothing. Try richest signature first.
    mode = job.mode if job.mode and "Soon" not in job.mode else None
    try:
        runner(mode=mode, log=log_callback)
    except TypeError:
        try:
            runner(log=log_callback)
        except TypeError:
            runner()


def _run_job(job: Job, tool) -> None:
    try:
        _emit(job, f"Starting {tool.name}...")
        if not tool.path.exists():
            _emit(job, f"File not found: {tool.path}", "error")
            job.status = "error"
            return

        _emit(job, f"Script path: {tool.path}")
        if job.mode:
            _emit(job, f"Mode: {job.mode}")

        if tool.type == "cli" and tool.runner:
            _run_cli(job, tool)
        else:
            _run_native(job, tool)

        if job.status == "running":
            if job.return_code in (None, 0):
                _emit(job, "✅ Completed successfully", "success")
                job.status = "done"
            else:
                _emit(job, f"⚠️ Exited with code {job.return_code}", "warning")
                job.status = "done"
    except Exception as exc:  # noqa: BLE001 - surface every failure to the UI
        import traceback

        _emit(job, f"❌ Error: {exc}", "error")
        _emit(job, traceback.format_exc(), "error")
        job.status = "error"
    finally:
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        _save_job_meta(job)
        HUB.broadcast(job.id, {"type": "status", "status": job.status,
                               "return_code": job.return_code})


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
@app.get("/api/tools")
def api_tools():
    result = []
    for tool in TOOLS:
        data = tool.to_dict()
        ok, missing = check_dependencies(tool.requires)
        data["dependencies_ok"] = ok
        data["missing"] = missing
        result.append(data)
    return JSONResponse(result)


@app.get("/api/tools/{tool_id}")
def api_tool(tool_id: str):
    tool = get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    data = tool.to_dict()
    ok, missing = check_dependencies(tool.requires)
    data["dependencies_ok"] = ok
    data["missing"] = missing
    return JSONResponse(data)


@app.post("/api/tools/{tool_id}/run")
def api_run(tool_id: str, payload: Optional[dict] = None):
    tool = get_tool(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    mode = (payload or {}).get("mode")
    job = Job(id=uuid.uuid4().hex[:12], tool_id=tool.id, tool_name=tool.name, mode=mode)

    with JOBS_LOCK:
        JOBS[job.id] = job

    job.thread = threading.Thread(target=_run_job, args=(job, tool), daemon=True)
    job.thread.start()

    return {"job_id": job.id, "status": job.status}


@app.post("/api/jobs/{job_id}/stop")
def api_stop(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        try:
            from .ecrm_routes import ECRM_JOBS
            ej = ECRM_JOBS.get(job_id)
        except Exception:
            ej = None
        if ej:
            ej.status = "stopped"
            if ej.context: ej.context.cancel()
            return {"job_id": job_id, "status": "stopped"}
        raise HTTPException(status_code=404, detail="Job not found")
    if job.process and job.process.poll() is None:
        job.process.terminate()
        _emit(job, "Process terminated by user.", "warning")
        job.status = "stopped"
    else:
        _emit(job, "Stop requested (job not process-based).", "warning")
        job.status = "stopped"
    return {"job_id": job.id, "status": job.status}


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    job = JOBS.get(job_id)
    if job:
        return {"job_id":job.id,"tool_id":job.tool_id,"tool_name":job.tool_name,"mode":job.mode,"status":job.status,"return_code":job.return_code,"started_at":job.started_at,"finished_at":job.finished_at,"output_file":getattr(job,"output_file",""),"records":getattr(job,"records_total",0),"progress":getattr(job,"progress",0.0),"lines":job.lines}
    pj=PERSISTED_JOBS.get(job_id)
    if pj:
        return {**pj,"tool_name":pj.get("tool", ""),"return_code":0 if pj.get("status")=="done" else None,"lines":[]}
    try:
        from .ecrm_routes import ECRM_JOBS
        ej=ECRM_JOBS.get(job_id)
    except Exception:
        ej=None
    if ej:
        return {"job_id":ej.id,"tool_id":"ecrm","tool_name":"ECRM Extractor","mode":ej.request.mode,"status":ej.status,"return_code":0 if ej.status=="done" else None,"started_at":ej.started_at,"finished_at":ej.finished_at,"output_file":getattr(ej,"output_file",""),"lines":ej.lines}
    raise HTTPException(status_code=404, detail="Job not found")


@app.websocket("/ws/logs/{job_id}")
async def ws_logs(websocket: WebSocket, job_id: str):
    # Jobs come from two registries: the generic launcher (JOBS) and the
    # dedicated ECRM web UI (ECRM_JOBS). Both share the same log protocol.
    job = JOBS.get(job_id)
    is_ecrm = False
    if not job:
        from .ecrm_routes import ECRM_JOBS
        job = ECRM_JOBS.get(job_id)
        is_ecrm = job is not None
    if not job:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    # Attach the running loop so worker threads can push asynchronously.
    try:
        import asyncio

        websocket._loop = asyncio.get_running_loop()  # type: ignore[attr-defined]
    except Exception:
        pass

    HUB.register(job_id, websocket)
    try:
        # Replay everything captured so far.
        for entry in job.lines:
            await websocket.send_json({"type": "log", **entry})
        if is_ecrm:
            await websocket.send_json({"type": "status", "status": job.status,
                                       "output_file": job.output_file})
        else:
            await websocket.send_json({"type": "status", "status": job.status,
                                       "return_code": job.return_code})
        while True:
            # Keep the connection open; we don't expect inbound messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        HUB.unregister(job_id, websocket)


@app.get("/api/dashboard")
def dashboard_data():
    """Return only measured runtime/persisted execution data."""
    rows=[]
    for pj in PERSISTED_JOBS.values():
        rows.append(dict(pj))
    for j in JOBS.values():
        item={"job_id":j.id,"tool_id":j.tool_id,"tool":j.tool_name,"mode":j.mode or "—","status":j.status,"started_at":j.started_at,"finished_at":j.finished_at,"output_file":getattr(j,"output_file",""),"records":getattr(j,"records_total",0),"input_files":getattr(j,"input_files",0)}
        rows=[r for r in rows if r.get("job_id")!=j.id]+[item]
    try:
        from .ecrm_routes import ECRM_JOBS
        for j in ECRM_JOBS.values():
            rec=0
            try: rec=_count_excel_rows(Path(j.output_file)) if j.output_file else 0
            except Exception: pass
            item={"job_id":j.id,"tool_id":"ecrm","tool":"ECRM Extractor","mode":j.request.mode,"status":j.status,"started_at":j.started_at,"finished_at":j.finished_at,"output_file":j.output_file,"records":rec,"input_files":1 if j.request.file_path else 0}
            rows=[r for r in rows if r.get("job_id")!=j.id]+[item]
    except Exception:
        pass
    rows.sort(key=lambda x:x.get("started_at") or "", reverse=True)
    total=len(rows); completed=sum(r.get("status")=="done" for r in rows); failed=sum(r.get("status")=="error" for r in rows); running=sum(r.get("status")=="running" for r in rows)
    files=sum(1 for r in rows if r.get("output_file") and Path(str(r.get("output_file"))).exists())
    records=sum(int(r.get("records") or 0) for r in rows)
    from collections import defaultdict
    daily=defaultdict(lambda:{"total":0,"completed":0,"failed":0})
    tools=defaultdict(int)
    today=datetime.now().date()
    for r in rows:
        try: dt=datetime.fromisoformat(str(r.get("started_at"))).date()
        except Exception: continue
        delta=(today-dt).days
        if 0<=delta<7:
            key=dt.strftime("%b %d")
            daily[key]["total"]+=1
            daily[key]["completed"]+=int(r.get("status")=="done")
            daily[key]["failed"]+=int(r.get("status")=="error")
        tools[r.get("tool") or "Unknown"]+=1
    daily_list=[]
    for i in range(6,-1,-1):
        dt=today.__class__.fromordinal(today.toordinal()-i)
        key=dt.strftime("%b %d")
        daily_list.append({"label":key,**daily[key]})
    return {"total_jobs":total,"completed":completed,"failed":failed,"running":running,"files":files,"records":records,"daily":daily_list,"tools":dict(tools),"mode_counts":dict(tools),"recent":rows[:50],"data_source":"runtime_jobs_only","generated_at":datetime.now().isoformat(timespec="seconds")}

# ---------------------------------------------------------------------------
# Static front-end
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    # Main application is the Automation Suite. ECRM is a child tool.
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                 "Pragma": "no-cache"},
    )

@app.get("/ecrm")
def ecrm_page():
    return FileResponse(
        STATIC_DIR / "ecrm.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                 "Pragma": "no-cache"},
    )

@app.get("/api/build")
def build_info():
    return {"app": "WE Automation Suite", "ui": "Enterprise Web", "build": "2026-09-19-v13-real-dashboard"}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()

# ============================================================================
# FULL WEB TOOL ROUTES
# All legacy Tkinter launch points are exposed through browser forms. The
# automation engines remain server-side and no desktop UI is required.
# ============================================================================
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
import tempfile, shutil, traceback

@app.get('/tool/{tool_id}')
def web_tool_page(tool_id: str):
    allowed = {'wo_unified','db','ftth_portal','psc'}
    if tool_id not in allowed:
        raise HTTPException(status_code=404, detail='Tool web page not found')
    return FileResponse(STATIC_DIR / 'tool.html', headers={'Cache-Control':'no-store'})


def _new_web_job(tool_id, mode=None):
    tool = get_tool(tool_id)
    if not tool: raise HTTPException(status_code=404, detail='Tool not found')
    job = Job(id=uuid.uuid4().hex[:12], tool_id=tool.id, tool_name=tool.name, mode=mode)
    with JOBS_LOCK: JOBS[job.id] = job
    return job


def _count_excel_rows(path: Path) -> int:
    try:
        import pandas as pd
        if path.exists() and path.suffix.lower() in {".xlsx", ".xls"}:
            return int(len(pd.read_excel(path)))
    except Exception:
        pass
    return 0


def _run_web_tool(job, fn):
    try:
        _emit(job, f'🌐 Starting {job.tool_name}…')
        fn()
        if job.status == 'running':
            job.return_code = 0
            job.progress = 100.0
            job.status = 'done'
            _emit(job, '✅ Completed successfully', 'success')
    except Exception as exc:
        job.return_code = 1
        job.status = 'error'
        _emit(job, f'❌ {type(exc).__name__}: {exc}', 'error')
        _emit(job, traceback.format_exc(), 'error')
    finally:
        job.finished_at = datetime.now().isoformat(timespec='seconds')
        HUB.broadcast(job.id, {'type':'status','status':job.status,'return_code':job.return_code,'output_file':getattr(job,'output_file','')})

@app.post('/api/webtools/wo_unified/run')
async def web_wo_run(files: List[UploadFile] = File(...), mode: str = Form('GPON')):
    job = _new_web_job('wo_unified', mode)
    root = Path(tempfile.mkdtemp(prefix='we_wo_'))
    def work():
        try:
            target = mode if mode in {'GPON','Fiber','Local Loop','WiMax'} else 'GPON'
            folder = root / target; folder.mkdir(parents=True, exist_ok=True)
            for f in files:
                dest = folder / Path(f.filename or 'input.pdf').name
                with dest.open('wb') as out:
                    shutil.copyfileobj(f.file, out)
            import importlib.util
            spec=importlib.util.spec_from_file_location('wo_unified_web', BASE_DIR/'WO Unified'/'wo_unified_runner.py')
            mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
            # Keep outputs inside the temporary job directory.
            old_out = mod.DEFAULT_OUTPUT_FOLDER; mod.DEFAULT_OUTPUT_FOLDER = str(root/'output')
            mod.run_wo_unified(str(root), mode=target, log=lambda m: _emit(job,m))
            out = root/'output'/mod.DEFAULT_OUTPUT_FILENAME
            if out.exists():
                job.output_file = str(out)
                job.records_total = _count_excel_rows(out)
                _emit(job, f'OUTPUT_FILE::{out}')
        finally:
            pass
    job.thread=threading.Thread(target=_run_web_tool,args=(job,work),daemon=True); job.thread.start()
    return {'job_id':job.id,'status':job.status}

@app.post('/api/webtools/db/run')
async def web_db_run(file: UploadFile = File(...), action: str = Form('validate'), service_type: str = Form('fiber'), username: str = Form(''), password: str = Form(''), selected_fields: str = Form('')):
    job=_new_web_job('db', f'{action}:{service_type}')
    root=Path(tempfile.mkdtemp(prefix='we_db_')); inp=root/(Path(file.filename or 'input.xlsx').name)
    with inp.open('wb') as out: shutil.copyfileobj(file.file,out)
    fields=[x.strip() for x in selected_fields.split(',') if x.strip()]
    def work():
        sys.path.insert(0,str(BASE_DIR/'DB'))
        from services.browser import create_driver, login
        from core.processor import process_rows
        try:
            from config import USERNAME as CFG_USER, PASSWORD as CFG_PASS
        except Exception:
            CFG_USER, CFG_PASS = '', ''
        use_user = username.strip() or str(CFG_USER or '').strip()
        use_pass = password or str(CFG_PASS or '')
        import pandas as pd
        df=pd.read_excel(inp)
        job.records_total = int(len(df))
        _emit(job,f'Loaded {len(df)} rows')
        driver=create_driver(headless=True)
        try:
            login(driver,use_user,use_pass,logger=lambda m:_emit(job,m))
            def progress(i,*args):
                pct=(float(i)/max(1,len(df)))*100 if isinstance(i,(int,float)) else 0
                job.progress=max(0.0,min(100.0,pct))
                HUB.broadcast(job.id,{'type':'progress','value':pct,'status':f'Processing {i}/{len(df)}'})
            result=process_rows(df,driver,action,service_type,lambda m:_emit(job,m),selected_fields=fields or None,progress_callback=progress)
            out=root/'DB_Output.xlsx'
            df.to_excel(out,index=False)
            job.output_file=str(out)
            _emit(job,f'OUTPUT_FILE::{out}')
            _emit(job,f'✅ Saved {len(df)} rows to {out}')
        finally: driver.quit()
    job.thread=threading.Thread(target=_run_web_tool,args=(job,work),daemon=True); job.thread.start(); return {'job_id':job.id,'status':job.status}

@app.post('/api/webtools/ftth_portal/run')
async def web_ftth_run(file: UploadFile = File(...), username: str = Form(''), password: str = Form('')):
    job=_new_web_job('ftth_portal')
    root=Path(tempfile.mkdtemp(prefix='we_ftth_')); inp=root/(Path(file.filename or 'input.xlsx').name)
    with inp.open('wb') as out: shutil.copyfileobj(file.file,out)
    def work():
        import importlib.util
        spec=importlib.util.spec_from_file_location('ftth_web',BASE_DIR/'FTTH portal'/'ftth_we_portal.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        out=root/'FTTH_Output.xlsx'
        try:
            import pandas as pd
            job.records_total = int(len(pd.read_excel(inp)))
        except Exception:
            pass
        # Web mode uses saved credentials; CAPTCHA interaction is intentionally
        # surfaced as a log/error instead of opening Tkinter.
        def wait_for_captcha(image_bytes, saved_user, saved_pass, attempt, max_attempts):
            cap=root/f'captcha_{attempt}.png'
            cap.write_bytes(image_bytes)
            job.captcha_image=str(cap)
            job.captcha_value=''
            job.captcha_event.clear()
            _emit(job, f'CAPTCHA_REQUIRED::{attempt}::{cap}', 'warning')
            HUB.broadcast(job.id, {'type':'captcha','attempt':attempt,'image_url':f'/api/jobs/{job.id}/captcha?attempt={attempt}'})
            if not job.captcha_event.wait(timeout=300):
                raise TimeoutError('CAPTCHA entry timed out after 5 minutes')
            value=job.captcha_value.strip()
            if not value:
                raise ValueError('CAPTCHA was empty')
            return {'username': username or saved_user, 'password': password or saved_pass, 'captcha': value}
        mod.run_ftth_portal(str(inp),str(out),log=lambda m:_emit(job,m),username=username,password=password,wait_for_captcha=wait_for_captcha)
        if out.exists(): job.output_file=str(out); _emit(job,f'OUTPUT_FILE::{out}')
    job.thread=threading.Thread(target=_run_web_tool,args=(job,work),daemon=True); job.thread.start(); return {'job_id':job.id,'status':job.status}

@app.post('/api/webtools/psc/run')
async def web_psc_run(file: UploadFile = File(...), username: str = Form(''), password: str = Form(''), domain: str = Form('CAIRO.TELECOMEGYPT.CORP')):
    job=_new_web_job('psc')
    root=Path(tempfile.mkdtemp(prefix='we_psc_')); inp=root/(Path(file.filename or 'input.xlsx').name)
    with inp.open('wb') as out: shutil.copyfileobj(file.file,out)
    def work():
        import importlib.util
        spec=importlib.util.spec_from_file_location('psc_web',BASE_DIR/'PSC extractor'/'Run.py')
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        out=root/'PSC_Output.xlsx'
        try:
            import pandas as pd
            job.records_total = int(len(pd.read_excel(inp)))
        except Exception:
            pass
        mod.run_extraction(str(inp),username=username,password=password,domain=domain,log=lambda m:_emit(job,m),output_file=str(out))
        if out.exists(): job.output_file=str(out); _emit(job,f'OUTPUT_FILE::{out}')
    job.thread=threading.Thread(target=_run_web_tool,args=(job,work),daemon=True); job.thread.start(); return {'job_id':job.id,'status':job.status}


@app.get('/api/webtools/{tool_id}/credentials')
def web_tool_credentials(tool_id: str):
    cfgs={
      'db': BASE_DIR/'DB'/'config.json',
      'ftth_portal': BASE_DIR/'FTTH portal'/'config.json',
      'psc': BASE_DIR/'PSC extractor'/'config.json',
    }
    path=cfgs.get(tool_id)
    data={}
    if path and path.exists():
        try: data=json.loads(path.read_text(encoding='utf-8'))
        except Exception: data={}
    return {'username':data.get('username',''),'domain':data.get('domain','CAIRO.TELECOMEGYPT.CORP')}

@app.get('/api/jobs/{job_id}/captcha')
def web_job_captcha(job_id: str):
    job=JOBS.get(job_id)
    if not job or not job.captcha_image:
        raise HTTPException(status_code=404, detail='CAPTCHA image not available')
    path=Path(job.captcha_image)
    if not path.exists(): raise HTTPException(status_code=404, detail='CAPTCHA image expired')
    return FileResponse(path, media_type='image/png')

@app.post('/api/jobs/{job_id}/captcha')
def web_job_captcha_submit(job_id: str, payload: dict):
    job=JOBS.get(job_id)
    if not job: raise HTTPException(status_code=404, detail='Job not found')
    value=str(payload.get('captcha') or '').strip()
    if not value: raise HTTPException(status_code=400, detail='CAPTCHA is required')
    job.captcha_value=value
    job.captcha_event.set()
    _emit(job,'CAPTCHA entered. Continuing login…','success')
    return {'ok':True}

@app.get('/api/jobs/{job_id}/download')
def download_web_job(job_id: str):
    job=JOBS.get(job_id)
    if not job:
        try:
            from .ecrm_routes import ECRM_JOBS
            ej=ECRM_JOBS.get(job_id)
        except Exception:
            ej=None
        if ej and ej.output_file:
            path=Path(ej.output_file)
            if not path.exists(): raise HTTPException(status_code=404, detail='Result file not found')
            return FileResponse(path, filename=path.name, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        raise HTTPException(status_code=404, detail='Result file not available')
    if not getattr(job,'output_file',''):
        raise HTTPException(status_code=404, detail='Result file not available')
    path=Path(job.output_file)
    if not path.exists(): raise HTTPException(status_code=404, detail='Result file not found')
    return FileResponse(path, filename=path.name, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
