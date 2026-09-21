"""
Registry of automation tools exposed to the web launcher.

This mirrors the PROJECTS list that used to live inside ``launcher.py``.
Each entry describes how to launch a tool and which Python packages it needs.

The web launcher never re-implements automation logic; it simply runs the
existing scripts as subprocesses (or calls their runner functions) and streams
their output back to the browser.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# BASE_DIR points at the repository root (the folder that contains launcher.py,
# ECRM/, DB/, etc.). tools.py lives inside webapp/, so we go one level up.
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class Tool:
    id: str
    name: str
    description: str
    icon: str
    color: str
    path: Path
    # "native"  -> run ``path`` as a standalone script (subprocess)
    # "cli"     -> import ``path`` and call the ``runner`` function in-process
    # "web"     -> the tool has its own browser UI; open ``web_page`` instead
    type: str = "native"
    runner: Optional[str] = None
    requires: List[str] = field(default_factory=list)
    # Optional list of selectable modes shown in the UI (e.g. GPON / Fiber).
    modes: List[str] = field(default_factory=list)
    # For type == "web": the in-app URL that opens the tool's own page.
    web_page: Optional[str] = None
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "color": self.color,
            "type": self.type,
            "runner": self.runner,
            "requires": self.requires,
            "modes": self.modes,
            "web_page": self.web_page,
            "path": str(self.path),
            "exists": self.path.exists(),
        }


TOOLS: List[Tool] = [
    Tool(
        id="wo_unified",
        name="WO Extractor",
        description="Choose GPON or Fiber extractor and save output into separate folders.",
        icon="📦",
        color="#2dd4bf",
        path=BASE_DIR / "WO Unified" / "wo_unified_runner.py",
        type="web",
        runner="run_wo_unified",
        web_page="/tool/wo_unified",
        requires=["PyPDF2", "pandas", "openpyxl"],
        modes=["GPON", "Fiber", "Local Loop (Soon)", "Wi-Max (Soon)", "VDSL (Soon)"],
    ),
    Tool(
        id="ecrm",
        name="ECRM Extractor",
        description="Extract customer and order data from ECRM — now with a full web UI.",
        icon="🔍",
        color="#5b2d91",
        path=BASE_DIR / "ECRM" / "main.py",
        # ECRM was converted to a browser app; the card opens /ecrm (see
        # webapp/static/ecrm.html + webapp/ecrm_routes.py) instead of spawning
        # the Tkinter window.
        type="web",
        web_page="/ecrm",
        requires=["requests", "pandas", "openpyxl"],
    ),
    Tool(
        id="db",
        name="DB Automation",
        description="Data entry automation for FTTH / Fiber / WiMax",
        icon="🗄️",
        color="#009688",
        path=BASE_DIR / "DB" / "main.py",
        type="web",
        web_page="/tool/db",
        requires=["selenium", "pandas", "openpyxl"],
    ),
    Tool(
        id="ftth_portal",
        name="FTTH Portal",
        description="Extract FTTH Portal data (KAM Orders)",
        icon="🌐",
        color="#607d8b",
        path=BASE_DIR / "FTTH portal" / "ftth_we_portal.py",
        type="web",
        web_page="/tool/ftth_portal",
        requires=["selenium", "pandas", "openpyxl"],
    ),
    Tool(
        id="psc",
        name="PSC Extractor",
        description="Extract PSC Requests data using Playwright",
        icon="⚡",
        color="#ff9800",
        path=BASE_DIR / "PSC extractor" / "Run.py",
        type="web",
        web_page="/tool/psc",
        requires=["playwright", "pandas", "openpyxl"],
    ),
]


PACKAGE_ALTERNATIVES = {
    "pypdf2": ["PyPDF2", "pypdf"],
    "pypdf": ["pypdf", "PyPDF2"],
    "fitz": ["fitz", "pymupdf"],
    "playwright": ["playwright"],
    "pillow": ["PIL"],
    "webdriver-manager": ["webdriver_manager"],
}


def get_tool(tool_id: str) -> Optional[Tool]:
    for tool in TOOLS:
        if tool.id == tool_id:
            return tool
    return None
