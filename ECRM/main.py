
import sys
sys.dont_write_bytecode = True

import os
import threading
import time
import subprocess
import webbrowser
from pathlib import Path

from ecrm_extractor.core.session import load_credentials
from ecrm_extractor.gui import EcrmApp


BASE_DIR = Path(__file__).resolve().parent.parent
WEB_URL = "http://127.0.0.1:8000"


class WebServer:
    def __init__(self):
        self.process = None

    def start(self):
        # Start the bundled FastAPI server from the project root so imports
        # such as webapp.ecrm_routes resolve correctly.
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "webapp.server:app",
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass


def main():
    server = WebServer()
    server.start()
    time.sleep(0.8)

    # The GUI now uses the Web API for extraction by default.
    app = EcrmApp(load_credentials=load_credentials, on_start=lambda gui: None)

    def on_close():
        server.stop()

    original_close = app.root.protocol("WM_DELETE_WINDOW")
    # Keep the GUI's own cleanup, then stop uvicorn.
    def close():
        try:
            app._on_closing()
        finally:
            server.stop()

    app.root.protocol("WM_DELETE_WINDOW", close)
    app.run()


if __name__ == "__main__":
    main()
