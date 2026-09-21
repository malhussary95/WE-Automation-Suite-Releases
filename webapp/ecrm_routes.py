"""
Web (FastAPI) backend for the ECRM Extractor tool.

It exposes the exact same workflow the desktop GUI offers — credentials, mode,
direct values / Excel file, field selection, presets, debug mode, live log and
progress, cancel, and a downloadable result file — but driven from the browser.

The heavy lifting is still done by ``ECRM/ecrm_extractor`` unchanged. We only
swap the CustomTkinter ``EcrmApp`` for ``WebGuiContext`` (see
``webapp/ecrm_adapter.py``) and stream its status to the page over the WebSocket
hub that already powers the other tools.
"""

from __future__ import annotations
import importlib.util
import sys
import os
import getpass
import base64
import ctypes
from ctypes import wintypes
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from .ecrm_adapter import BASE_DIR, ECRM_DIR, EcrmRequest, WebGuiContext

if str(ECRM_DIR) not in sys.path:
    sys.path.insert(0, str(ECRM_DIR))

router = APIRouter(prefix="/api/ecrm", tags=["ecrm"])

UPLOAD_DIR = BASE_DIR / "webapp" / "uploads"
ECRM_OUTPUT_DIR = ECRM_DIR / "output"

def _normalize_windows_user(value: str) -> str:
    """Normalize DOMAIN\\user / user@domain / plain user for comparison."""
    value = str(value or "").strip()
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value.strip().casefold()


def _password_store_file() -> Path:
    """Per-Windows-user encrypted password store."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    folder = Path(base) / "WE_ECRM_Extractor"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "ecrm_password.dpapi"


def _dpapi_protect(value: str) -> str:
    """Encrypt a password using Windows DPAPI for the current user."""
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is required for remembered ECRM passwords.")

    raw = value.encode("utf-8")
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    in_buf = ctypes.create_string_buffer(raw)
    in_blob = DATA_BLOB(len(raw), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "WE ECRM Password",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise RuntimeError("Windows DPAPI encryption failed.")

    try:
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(value: str) -> str:
    """Decrypt a password previously protected for the current Windows user."""
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is required for remembered ECRM passwords.")

    encrypted = base64.b64decode(value.encode("ascii"))
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    in_buf = ctypes.create_string_buffer(encrypted)
    in_blob = DATA_BLOB(len(encrypted), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise RuntimeError("This saved ECRM password cannot be decrypted by the current Windows user.")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _save_remembered_password(password: str) -> None:
    """Save encrypted password for this Windows user only."""
    if not password:
        return
    _password_store_file().write_text(
        _dpapi_protect(password),
        encoding="utf-8",
    )


def _load_remembered_password() -> str:
    """Load the saved password for this Windows user, or return empty."""
    path = _password_store_file()
    if not path.exists():
        return ""
    try:
        return _dpapi_unprotect(path.read_text(encoding="utf-8").strip())
    except Exception:
        # Another Windows user cannot decrypt this file; treat it as absent.
        return ""


def _current_windows_user() -> str:
    """Return the ECRM username of the Windows account running this backend."""
    # ECRM username is the Windows USERNAME (for example: x).
    # The domain is intentionally not prepended because ECRM normally expects
    # the account name itself. Domain/account binding is still enforced by
    # comparing the normalized username on every extraction request.
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or getpass.getuser()
        or ""
    ).strip()


# ---------------------------------------------------------------------------
# Static metadata (fields / presets / modes) straight from the ECRM package
# ---------------------------------------------------------------------------
def _load_fields():
    """Import FIELD_OPTIONS / FIELD_PRESETS from the ECRM package."""
    from ecrm_extractor.fields import FIELD_OPTIONS, FIELD_PRESETS  # type: ignore

    return list(FIELD_OPTIONS), dict(FIELD_PRESETS)


@dataclass
class EcrmJob:
    id: str
    request: EcrmRequest
    status: str = "running"          # running | done | error | stopped
    phase: str = "Starting"
    output_file: str = ""
    progress: float = 0.0
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    started_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None
    lines: List[dict] = field(default_factory=list)
    context: Optional[WebGuiContext] = None
    thread: Optional[threading.Thread] = None

    def append(self, message: str, level: str = "info") -> dict:
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "message": str(message),
            "level": level,
        }
        self.lines.append(entry)
        self.last_activity = datetime.now().isoformat(timespec="seconds")
        return entry


ECRM_JOBS: Dict[str, EcrmJob] = {}
ECRM_LOCK = threading.Lock()


def _broadcast(job_id: str, payload: dict) -> None:
    """Reuse the launcher's WebSocket hub if available."""
    try:
        from .server import HUB  # type: ignore

        HUB.broadcast(job_id, payload)
    except Exception:
        pass


def _emit(job: EcrmJob, message: str, level: str = "info") -> None:
    entry = job.append(message, level)
    _broadcast(job.id, {"type": "log", **entry})

def _phase(job: EcrmJob, name: str, detail: str = "") -> None:
    job.phase = name
    if detail:
        _emit(job, detail)
    _broadcast(job.id, {
        "type": "phase",
        "phase": name,
        "progress": job.progress,
    })


def _classify(line: str) -> str:
    lowered = line.lower()
    if "error" in lowered or "❌" in line or "traceback" in lowered or "failed" in lowered:
        return "error"
    if "warn" in lowered or "⚠" in line or "cancel" in lowered:
        return "warning"
    if "success" in lowered or "✅" in line or "done" in lowered or "completed" in lowered:
        return "success"
    return "info"


# ---------------------------------------------------------------------------
# Job runner watchdog / diagnostics
# ---------------------------------------------------------------------------
def _start_job_watchdog(job: EcrmJob) -> None:
    """Keep the browser informed even if the ECRM engine blocks on I/O."""
    def watch() -> None:
        last_reported = None
        while job.status == "running":
            time.sleep(3)
            if job.status != "running":
                break
            try:
                now = datetime.now()
                last = datetime.fromisoformat(job.last_activity)
                idle = max(0, int((now - last).total_seconds()))
            except Exception:
                idle = 0
            if idle >= 3:
                key = (job.phase, idle // 3)
                if key != last_reported:
                    last_reported = key
                    _emit(job, f"⏳ Still working — phase: {job.phase} (no new event for {idle}s)", "warning")
                    _broadcast(job.id, {
                        "type": "heartbeat",
                        "phase": job.phase,
                        "idle_seconds": idle,
                        "progress": job.progress,
                    })
    threading.Thread(target=watch, daemon=True, name=f"ecrm-watch-{job.id}").start()

# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------
def _run_ecrm_job(job: EcrmJob) -> None:
    _emit(job, "Worker entered successfully.")
    _phase(job, "Initializing", "Loading ECRM extraction engine…")
    # Late imports so a missing optional dep only fails this job, not the server.
    try:
        from ecrm_extractor.dependencies import build_extraction_dependencies  # type: ignore
        from ecrm_extractor.runner import run_extraction  # type: ignore
    except Exception as exc:  # noqa: BLE001
        _emit(job, f"❌ Cannot import ECRM engine: {exc}", "error")
        job.status = "error"
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        _broadcast(job.id, {"type": "status", "status": job.status, "output_file": ""})
        return

    def emit(message: str, level: Optional[str] = None) -> None:
        _emit(job, message, level or _classify(str(message)))

    def progress(pct: float, status: str) -> None:
        job.progress = max(0.0, min(100.0, float(pct)))
        if status:
            job.phase = str(status)
        job.last_activity = datetime.now().isoformat(timespec="seconds")
        _broadcast(job.id, {"type": "progress", "value": job.progress, "status": status, "phase": job.phase})

    ctx = WebGuiContext(job.request, emit=emit, progress_cb=progress)
    job.context = ctx

    # Capture the generated Excel path so the browser can download it.
    captured: Dict[str, str] = {}
    ctx.smart_result_callback = lambda rows, out_excel, headers: captured.update({"file": str(out_excel)})

    try:
        _phase(job, "Starting", f"Starting ECRM extraction (mode={ctx.mode}, fields={len(ctx.selected_fields)})…")
        if ctx.file_path:
            _emit(job, f"Input file: {ctx.file_path}")
        if ctx.direct_values:
            _emit(job, f"Direct values: {len(ctx.direct_values)}")
        if ctx.debug_mode:
            _emit(job, "Debug mode is ON", "warning")

        _phase(job, "Initializing", "Loading ECRM extraction dependencies…")
        deps = build_extraction_dependencies(ctx)
        _phase(job, "Running", "ECRM dependencies loaded. Starting extraction engine…")
        run_extraction(deps, ctx)

        job.output_file = captured.get("file", "")
        if job.status == "running":
            job.progress = 100.0
            job.phase = "Completed"
            job.status = "done"
            _emit(job, "✅ Extraction finished", "success")
    except Exception as exc:  # noqa: BLE001
        import traceback

        _emit(job, f"❌ {type(exc).__name__}: {exc}", "error")
        _emit(job, traceback.format_exc(), "error")
        job.status = "error"
    finally:
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        _broadcast(job.id, {
            "type": "status",
            "status": job.status,
            "output_file": job.output_file,
            "phase": job.phase,
            "progress": job.progress,
        })


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("/meta")
def ecrm_meta():
    """Fields, presets and modes the UI needs to render the form."""
    try:
        fields, presets = _load_fields()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Cannot load ECRM fields: {exc}")

    return JSONResponse({
        "fields": fields,
        "presets": presets,
        "modes": ["ORDER", "CID", "SO", "ORD"],
        "deps_ok": _deps_status(),
    })


def _deps_status():
    """Best-effort check that the ECRM runtime dependencies are importable."""
    required = {
        "requests": "requests",
        "requests_ntlm": "requests_ntlm",
        "pandas": "pandas",
        "openpyxl": "openpyxl",
    }
    missing = [pkg for mod, pkg in required.items() if importlib.util.find_spec(mod) is None]
    return {"ok": not missing, "missing": missing}


@router.get("/credentials")
def ecrm_credentials():
    """Return the detected Windows username and the remembered password, if any."""
    username = _current_windows_user()
    saved_password = _load_remembered_password()
    return {
        "username": username,
        "windows_user": username,
        "password": saved_password,
        "password_saved": bool(saved_password),
        "locked_to_windows_user": True,
        "password_required": not bool(saved_password),
        "source": "Windows/domain account",
    }


@router.post("/remember-password")
def remember_ecrm_password(payload: dict):
    """Encrypt and remember the password for the current Windows user."""
    username = _current_windows_user()
    requested_username = str(payload.get("username") or "").strip()
    if requested_username and (
        _normalize_windows_user(requested_username)
        != _normalize_windows_user(username)
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Password save rejected. This application is locked to Windows/domain "
                f"user '{username}'."
            )
        )

    password = str(payload.get("password") or "")
    if not password:
        raise HTTPException(status_code=400, detail="ECRM password is required.")

    try:
        _save_remembered_password(password)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cannot securely save ECRM password: {exc}"
        )

    return {
        "ok": True,
        "username": username,
        "password_saved": True,
        "storage": "Windows DPAPI / current user",
    }


@router.post("/upload")
async def ecrm_upload(file: UploadFile = File(...)):
    """Accept an Excel input file and return the path the backend will read."""
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx / .xls files are supported")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename).name}"
    dest = UPLOAD_DIR / safe_name
    content = await file.read()
    dest.write_bytes(content)
    return {"path": str(dest), "name": file.filename}


@router.post("/run")
def ecrm_run(payload: dict):
    mode = str(payload.get("mode") or "ORDER").upper()
    selected_fields = payload.get("selected_fields") or []
    direct_values = payload.get("direct_values") or []
    file_path = payload.get("file_path") or ""
    try:
        max_workers = max(1, min(int(payload.get("max_workers") or 5), 12))
    except (TypeError, ValueError):
        max_workers = 5

    if not selected_fields:
        raise HTTPException(status_code=400, detail="Select at least one field")
    if not direct_values and not file_path:
        raise HTTPException(status_code=400, detail="Provide values or an Excel file")

    # Username is detected from the Windows/domain account and cannot be
    # changed by the browser. The password is entered by the user.
    username = _current_windows_user()
    requested_username = str(payload.get("username") or "").strip()
    if requested_username and (
        _normalize_windows_user(requested_username)
        != _normalize_windows_user(username)
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Login rejected. This application is locked to Windows/domain user "
                f"'{username}'; another ECRM username cannot be used."
            )
        )

    password = str(payload.get("password") or "")
    if not password:
        password = _load_remembered_password()

    if not password:
        raise HTTPException(
            status_code=400,
            detail="ECRM password is required. Enter it once and save it."
        )

    # Save/update the password encrypted with Windows DPAPI. It can only be
    # decrypted under the same Windows user profile.
    try:
        _save_remembered_password(password)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Cannot securely save ECRM password: {exc}"
        )

    request = EcrmRequest(
        username=username,
        password=password,
        mode=mode,
        selected_fields=list(selected_fields),
        direct_values=list(direct_values),
        file_path=str(file_path),
        debug_mode=bool(payload.get("debug_mode")),
        max_workers=max_workers,
    )

    job = EcrmJob(id=uuid.uuid4().hex[:12], request=request)
    with ECRM_LOCK:
        ECRM_JOBS[job.id] = job

    # Write the first diagnostic line BEFORE starting the worker. This makes
    # the job visible even if the ECRM worker blocks during an import/session/API call.
    _emit(job, f"Job accepted: mode={mode}, items={len(direct_values) if direct_values else 0}, fields={len(selected_fields)}, workers={max_workers}")
    _emit(job, "Worker thread starting…")
    _broadcast(job.id, {"type": "status", "status": "running", "phase": "Starting", "progress": 0})

    _start_job_watchdog(job)
    job.thread = threading.Thread(target=_run_ecrm_job, args=(job,), daemon=True, name=f"ecrm-job-{job.id}")
    job.thread.start()
    return {"job_id": job.id, "status": job.status}


@router.post("/jobs/{job_id}/stop")
def ecrm_stop(job_id: str):
    job = ECRM_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.context:
        job.context.cancel()
    job.status = "stopped"
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}")
def ecrm_job(job_id: str):
    job = ECRM_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "phase": job.phase,
        "progress": job.progress,
        "last_activity": job.last_activity,
        "output_file": job.output_file,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "lines": job.lines,
    }


@router.get("/jobs/{job_id}/download")
def ecrm_download(job_id: str):
    job = ECRM_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.output_file:
        raise HTTPException(status_code=404, detail="No output file for this job")
    path = Path(job.output_file)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file no longer exists")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/history")
def ecrm_history():
    """List previously generated Excel files (newest first)."""
    if not ECRM_OUTPUT_DIR.exists():
        return JSONResponse([])
    files = sorted(ECRM_OUTPUT_DIR.glob("ECRM_OUTPUT_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
    return JSONResponse([
        {
            "name": p.name,
            "size": p.stat().st_size,
            "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        }
        for p in files[:50]
    ])


@router.get("/history/{name}")
def ecrm_history_download(name: str):
    # Guard against path traversal.
    if "/" in name or "\\" in name or not name.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Invalid file name")
    path = ECRM_OUTPUT_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@router.get("/diagnostic")
def ecrm_diagnostic():
    return {
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "jobs": [
            {"job_id": j.id, "status": j.status, "phase": j.phase, "progress": j.progress, "last_activity": j.last_activity, "lines": len(j.lines)}
            for j in list(ECRM_JOBS.values())[-10:]
        ],
    }
