"""
Headless adapter that lets the ECRM extraction engine (``ECRM/ecrm_extractor``)
run inside the web backend instead of a CustomTkinter window.

The engine was written against a "gui" object (``EcrmApp``) that exposes widget
state as plain attributes plus a few helper methods. Instead of rewriting the
engine, we provide a small object that mimics exactly the surface it touches:

    file_path, direct_values, username, password, mode, selected_fields,
    debug_mode, progress, status_var, messagebox
    is_cancelled(), reset_ui(), smart_result_callback(), root

Every UI touch is routed to a callback so the web layer can push it to the
browser over its existing log/status WebSocket.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional


# ---------------------------------------------------------------------------
# Make the ECRM package importable no matter what the current directory is.
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
ECRM_DIR = BASE_DIR / "ECRM"
if str(ECRM_DIR) not in sys.path:
    sys.path.insert(0, str(ECRM_DIR))


@dataclass
class EcrmRequest:
    """Everything the browser sends to start an extraction."""

    username: str = ""
    password: str = ""
    mode: str = "ORDER"
    selected_fields: List[str] = field(default_factory=list)
    # Either paste values (one list) or an uploaded Excel file path.
    direct_values: List[str] = field(default_factory=list)
    file_path: str = ""
    debug_mode: bool = False
    max_workers: int = 5


class _Var:
    """Minimal stand-in for a tkinter StringVar (only ``.set`` is used)."""

    def __init__(self, on_set: Optional[Callable[[str], None]] = None, value: str = "") -> None:
        self._value = value
        self._on_set = on_set

    def set(self, value: str) -> None:
        self._value = value
        if self._on_set:
            self._on_set(str(value))

    def get(self) -> str:
        return self._value


class _Progress:
    """Stand-in for CTkProgressBar; ``set`` receives a 0..1 float."""

    def __init__(self, on_set: Callable[[float], None]) -> None:
        self._on_set = on_set

    def set(self, value: float) -> None:
        self._on_set(float(value))


class _MessageBox:
    """Stand-in for tkinter.messagebox — pushes messages to the web log."""

    def __init__(self, emit: Callable[[str, str], None]) -> None:
        self._emit = emit

    def showinfo(self, title: str, message: str) -> None:
        self._emit(f"{title}: {message}", "success")

    def showerror(self, title: str, message: str) -> None:
        self._emit(f"{title}: {message}", "error")

    def showwarning(self, title: str, message: str) -> None:
        self._emit(f"{title}: {message}", "warning")

    def askyesno(self, title: str, message: str, **_) -> bool:  # noqa: D401
        # No native dialog available in the web context — default to "yes" so
        # non-blocking confirmations do not stall the extraction.
        self._emit(f"{title}: {message} (auto-confirmed)", "warning")
        return True


class WebGuiContext:
    """
    A fake ``EcrmApp`` good enough for ``run_extraction`` to run headless.

    ``emit`` is called with ``(message, level)`` for every status/progress/notice
    so the web layer can stream it to the browser.
    """

    def __init__(
        self,
        request: EcrmRequest,
        emit: Callable[[str, str], None],
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> None:
        self._emit = emit
        self._progress_cb = progress_cb

        # ---- state the engine reads directly -------------------------------
        self.file_path = request.file_path or ""
        self.direct_values = list(request.direct_values or [])
        self.username = request.username or ""
        self.password = request.password or ""
        self.mode = (request.mode or "ORDER").upper()
        self.selected_fields = set(request.selected_fields or [])
        self.debug_mode = bool(request.debug_mode)
        try:
            self.max_workers = max(1, min(int(request.max_workers or 5), 12))
        except (TypeError, ValueError):
            self.max_workers = 5

        # ---- UI stand-ins --------------------------------------------------
        self.status_var = _Var(lambda value: emit(value, "info"))
        self.status_color_var = _Var()
        self.progress = _Progress(self._on_progress)
        self.messagebox = _MessageBox(emit)

        # ---- internal ------------------------------------------------------
        self._cancelled = False
        self._lock = threading.Lock()
        self._partial_results_count = 0
        self._last_progress = 0.0
        self.web_phase = "Starting"
        self.smart_result_callback: Optional[Callable] = None

        # ``show_error``/``run_on_ui`` call ``gui.root.after`` — a real tkinter
        # root would block; here ``after`` simply runs the callback inline.
        self.root = _FakeRoot(self)

    # -- progress plumbing ---------------------------------------------------
    def _on_progress(self, value: float) -> None:
        pct = max(0.0, min(100.0, value * 100.0))
        self._last_progress = pct
        if self._progress_cb:
            self._progress_cb(pct, "")

    # -- control from the web side ------------------------------------------
    def set_web_phase(self, phase: str) -> None:
        self.web_phase = str(phase or "Processing")
        self._emit(f"Phase: {self.web_phase}", "info")

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
        self._emit("Cancellation requested…", "warning")

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    # -- helpers referenced by ui_bridge ------------------------------------
    def reset_ui(self, reset_progress: bool = True) -> None:  # noqa: D401
        if reset_progress:
            self.progress.set(0.0)


class _FakeRoot:
    """Only ``after`` and ``update_idletasks`` are ever called on the root."""

    def __init__(self, ctx: WebGuiContext) -> None:
        self._ctx = ctx

    def after(self, _delay: int, callback: Callable, *args, **kwargs) -> None:
        # Run immediately (we are already on a worker thread in the web app).
        callback(*args, **kwargs)

    def update_idletasks(self) -> None:
        return None
