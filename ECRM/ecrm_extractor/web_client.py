
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

try:
    import requests
except Exception:
    requests = None


class EcrmWebClient:
    """Client for the bundled FastAPI ECRM backend."""

    def __init__(self, base_url="http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.job_id = None
        self._stop = False

    def _check(self):
        if requests is None:
            raise RuntimeError("requests is required for Web-connected mode.")

    def health(self, timeout=3):
        self._check()
        r = requests.get(f"{self.base_url}/api/ecrm/meta", timeout=timeout)
        r.raise_for_status()
        return r.json()

    def run(self, gui, on_finished: Optional[Callable] = None):
        self._check()
        payload = {
            "username": gui.username,
            "password": gui.password,
            "mode": gui.mode,
            "selected_fields": sorted(gui.selected_fields),
            "direct_values": list(gui.direct_values),
            "file_path": gui.file_path,
            "debug_mode": bool(gui.debug_mode),
            "max_workers": int(getattr(gui, "max_workers", 5) or 5),
        }
        r = requests.post(f"{self.base_url}/api/ecrm/run", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        self.job_id = data["job_id"]
        self._stop = False

        def poll():
            last_line_count = 0
            while not self._stop:
                try:
                    jr = requests.get(
                        f"{self.base_url}/api/ecrm/jobs/{self.job_id}",
                        timeout=10,
                    )
                    jr.raise_for_status()
                    job = jr.json()

                    lines = job.get("lines") or []
                    for entry in lines[last_line_count:]:
                        msg = entry.get("message", "")
                        level = entry.get("level", "info")
                        gui.root.after(0, lambda m=msg, lv=level: gui.web_log(m, lv))
                    last_line_count = len(lines)

                    # The bundled backend exposes progress through WebSocket
                    # only, while the job endpoint exposes logs/status.
                    status = str(job.get("status", "running"))
                    if status == "done":
                        gui.root.after(0, lambda j=job: gui.web_job_done(j))
                        break
                    if status in ("error", "stopped"):
                        gui.root.after(0, lambda j=job: gui.web_job_done(j))
                        break
                except Exception as exc:
                    gui.root.after(0, lambda e=exc: gui.web_log(f"Web polling error: {e}", "error"))
                    break
                time.sleep(0.7)

            if on_finished:
                gui.root.after(0, on_finished)

        threading.Thread(target=poll, daemon=True).start()
        return self.job_id

    def stop(self):
        self._stop = True
        if not self.job_id or requests is None:
            return
        try:
            requests.post(f"{self.base_url}/api/ecrm/jobs/{self.job_id}/stop", timeout=5)
        except Exception:
            pass
