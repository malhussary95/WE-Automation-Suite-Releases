"""
=================================================================
  WE Automation Tools - Unified Modern Launcher
  Responsive | Dark/Light Mode | DPI Aware | Project Cards
=================================================================
"""

import os
import sys
import json
import threading
import subprocess
import importlib.util
from pathlib import Path
from datetime import datetime
from typing import Dict, List

try:
    import customtkinter as ctk
    from customtkinter import (
        CTk, CTkFrame, CTkLabel, CTkButton, CTkScrollableFrame,
        CTkProgressBar, CTkImage, CTkEntry, CTkOptionMenu,
        CTkTextbox, CTkToplevel
    )
    from PIL import Image
except ImportError:
    print("Installing required packages: customtkinter, pillow...")
    os.system(f"{sys.executable} -m pip install customtkinter pillow --quiet")
    import customtkinter as ctk
    from customtkinter import (
        CTk, CTkFrame, CTkLabel, CTkButton, CTkScrollableFrame,
        CTkProgressBar, CTkImage, CTkEntry, CTkOptionMenu,
        CTkTextbox, CTkToplevel
    )
    from PIL import Image

# ============================================================
# CONFIGURATION & PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "launcher_config.json"

PROJECTS = [
    {
        "id": "wo_unified",
        "name": "WO Extractor",
        "description": "Choose GPON or Fiber extractor and save output into separate folders.",
        "icon": "📦",
        "color": "#2dd4bf",
        "path": BASE_DIR / "WO Unified" / "wo_unified_runner.py",
        "type": "cli",
        "runner": "run_wo_unified",
        "requires": ["PyPDF2", "pandas", "openpyxl"],
    },
    {
        "id": "ecrm",
        "name": "ECRM Extractor",
        "description": "Extract customer and order data from ECRM",
        "icon": "🔍",
        "color": "#5b2d91",
        "path": BASE_DIR / "ECRM" / "main.py",
        "type": "native",
        "requires": ["requests", "pandas", "openpyxl"],
    },
    {
        "id": "db",
        "name": "DB Automation",
        "description": "Data entry automation for FTTH / Fiber / WiMax",
        "icon": "🗄️",
        "color": "#009688",
        "path": BASE_DIR / "DB" / "main.py",
        "type": "native",
        "requires": ["selenium", "pandas", "openpyxl", "webdriver-manager"],
    },
    {
        "id": "ftth_portal",
        "name": "FTTH Portal",
        "description": "Extract FTTH Portal data (KAM Orders)",
        "icon": "🌐",
        "color": "#607d8b",
        "path": BASE_DIR / "FTTH portal" / "ftth_we_portal.py",
        "type": "native",
        "requires": ["selenium", "pandas", "openpyxl", "webdriver-manager"],
    },
    {
        "id": "psc",
        "name": "PSC Extractor",
        "description": "Extract PSC Requests data using Playwright",
        "icon": "⚡",
        "color": "#ff9800",
        "path": BASE_DIR / "PSC extractor" / "Run.py",
        "type": "native",
        "requires": ["playwright", "pandas", "openpyxl"],
    },
]

THEME = {
    "bg": ("#f7f5fb", "#120a20"),
    "surface": ("#ffffff", "#1a1029"),
    "surface_2": ("#f9f7fc", "#251537"),
    "surface_hover": ("#f0e9f8", "#34204b"),
    "border": ("#dfd4eb", "#443057"),
    "accent": ("#5b2d91", "#6b35a6"),
    "accent_hover": ("#4a2379", "#5b2d91"),
    "accent_soft": ("#eee4f7", "#332047"),
    "text_primary": ("#171022", "#fbf8ff"),
    "text_secondary": ("#74657f", "#c9bdd6"),
    "success": "#22c55e",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "info": "#3b82f6",
}

CARD_RADIUS = 12
CONTROL_RADIUS = 8


def get_font(size=13, weight="normal", family="Segoe UI"):
    try:
        return ctk.CTkFont(family=family, size=size, weight=weight if weight in ["normal", "bold"] else "normal")
    except:
        return ctk.CTkFont(size=size, weight=weight if weight in ["normal", "bold"] else "normal")


def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"theme": "Light", "geometry": "1200x800", "favorites": []}


def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Config save error: {e}")


def ensure_dependencies(packages):
    missing = []
    for pkg in packages:
        # القائمة البديلة لأسماء الاستيراد البرمجية لكل مكتبة
        # فمثلاً مكتبة pypdf2 قد تكون مثبتة باسم pypdf في الإصدارات الحديثة
        alternatives = {
            "pypdf2": ["PyPDF2", "pypdf"],
            "pypdf": ["pypdf", "PyPDF2"],
            "fitz": ["fitz", "pymupdf"],
            "playwright": ["playwright"],
            "pillow": ["PIL"],
            "webdriver-manager": ["webdriver_manager"],
        }.get(pkg.lower(), [pkg, pkg.lower()])

        found = False
        for name in alternatives:
            try:
                importlib.import_module(name)
                found = True
                break
            except ImportError:
                continue
        
        if not found:
            missing.append(pkg)
            
    return (len(missing) == 0), missing


class LogWindow(CTkToplevel):
    def __init__(self, parent, title, project_id):
        super().__init__(parent)
        self.title(f"🚀 {title}")
        self.project_id = project_id
        self.configure(fg_color=THEME["bg"][1 if ctk.get_appearance_mode() == "Dark" else 0])
        
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = int(pw * 0.75), int(ph * 0.75)
        x, y = px + (pw - w)//2, py + (ph - h)//2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(600, 400)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.frame = CTkFrame(self, fg_color=THEME["surface"], corner_radius=CARD_RADIUS, border_width=1, border_color=THEME["border"])
        self.frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)
        
        self.header = CTkFrame(self.frame, fg_color="transparent", height=40)
        self.header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 0))
        self.header.grid_columnconfigure(0, weight=1)
        
        CTkLabel(self.header, text=f"● Running: {title}", font=get_font(16, "bold"), text_color=THEME["accent"]).grid(row=0, column=0, sticky="w")
        
        self.status_label = CTkLabel(self.header, text="Ready", font=get_font(12), text_color=THEME["text_secondary"])
        self.status_label.grid(row=0, column=1, sticky="e", padx=10)
        
        self.log_text = CTkTextbox(
            self.frame,
            fg_color=THEME["surface_2"],
            text_color=THEME["text_primary"],
            font=get_font(12, "normal", "Consolas"),
            corner_radius=CONTROL_RADIUS,
            border_width=1,
            border_color=THEME["border"],
            wrap="word"
        )
        self.log_text.grid(row=1, column=0, padx=12, pady=12, sticky="nsew")
        self.log_text.configure(state="disabled")
        
        self.progress = CTkProgressBar(self.frame, height=6, corner_radius=3, progress_color=THEME["accent"], fg_color=THEME["border"])
        self.progress.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="ew")
        self.progress.set(0)
        
        self.controls = CTkFrame(self.frame, fg_color="transparent", height=40)
        self.controls.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        
        self.stop_btn = CTkButton(
            self.controls, text="⏹ Stop", width=100, height=32,
            fg_color=THEME["error"], hover_color="#dc2626", text_color="white",
            font=get_font(12, "bold"), corner_radius=CONTROL_RADIUS,
            command=self.stop_process
        )
        self.stop_btn.pack(side="right", padx=5)
        
        self.clear_btn = CTkButton(
            self.controls, text="🗑 Clear", width=100, height=32,
            fg_color=THEME["surface_hover"], hover_color=THEME["surface_2"],
            text_color=THEME["text_primary"], font=get_font(12),
            corner_radius=CONTROL_RADIUS, command=self.clear_log
        )
        self.clear_btn.pack(side="right", padx=5)
        
        self.is_running = False
        self.process = None
        
    def log(self, message, level="info"):
        self.log_text.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = {"info": THEME["text_primary"], "success": THEME["success"], 
                 "warning": THEME["warning"], "error": THEME["error"]}.get(level, THEME["text_primary"])
        
        self.log_text.insert("end", f"[{timestamp}] ", "timestamp")
        self.log_text.insert("end", f"{message}\n", level)
        
        # حل مشكلة Scaling Error: الوصول للمكون الداخلي لـ tkinter مباشرة
        # وتجهيز الألوان بناءً على الـ Theme الحالي لأن tkinter لا يفهم tuple الألوان
        mode = 1 if ctk.get_appearance_mode() == "Dark" else 0
        actual_ts_color = THEME["text_secondary"][mode]
        actual_level_color = color[mode] if isinstance(color, tuple) else color

        # استخدام _textbox للوصول لـ tag_config الأصلي وتجاوز قيود customtkinter
        self.log_text._textbox.tag_config("timestamp", foreground=actual_ts_color, font=("Consolas", 11))
        self.log_text._textbox.tag_config(level, foreground=actual_level_color, font=("Consolas", 12))
        
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        
    def set_status(self, text, color=THEME["text_secondary"]):
        self.status_label.configure(text=text, text_color=color)
        
    def set_progress(self, value):
        self.progress.set(max(0.0, min(1.0, value)))
        
    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        
    def stop_process(self):
        self.is_running = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.log("Process terminated by user.", "warning")
            self.set_status("Stopped", THEME["warning"])


class ProjectCard(CTkFrame):
    def __init__(self, parent, project, on_launch, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.project = project
        self.on_launch = on_launch
        self.unified_mode_var = None

        
        self.configure(
            fg_color=THEME["surface"],
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=THEME["border"],
            height=200
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self.accent = CTkFrame(self, fg_color=project["color"], height=4, corner_radius=0)
        self.accent.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        
        content = CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)  # تجعل الوصف يأخذ المساحة المتاحة ويدفع الـ Footer لأسفل
        
        header = CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        
        icon_label = CTkLabel(header, text=project["icon"], font=get_font(28))
        icon_label.grid(row=0, column=0, padx=(0, 10))
        
        title = CTkLabel(header, text=project["name"], font=get_font(16, "bold"), text_color=THEME["text_primary"])
        title.grid(row=0, column=1, sticky="w")
        
        desc = CTkLabel(
            content, 
            text=project["description"], 
            font=get_font(12), 
            text_color=THEME["text_secondary"],
            wraplength=280,
            justify="left"
        )
        desc.grid(row=1, column=0, sticky="nw", pady=(8, 0))

        # Unified WO UI (GPON / Fiber)
        if self.project.get("id") == "wo_unified":
            option_row = CTkFrame(content, fg_color="transparent")
            option_row.grid(row=2, column=0, sticky="ew", pady=(10, 6))

            CTkLabel(
                option_row,
                text="Extractor Type:",
                font=get_font(12),
                text_color=THEME["text_secondary"],
                anchor="w",
                justify="left",
            ).grid(row=0, column=0, sticky="w", padx=(0, 10))

            self.unified_mode_var = ctk.StringVar(value="GPON")
            CTkOptionMenu(
                option_row,
                values=[
                    "GPON", 
                    "Fiber", 
                    "Local Loop (Soon)", 
                    "Wi-Max (Soon)", 
                    "VDSL (Soon)"
                ],
                variable=self.unified_mode_var,
                width=120,
            ).grid(row=0, column=1, sticky="w")

        # جعل الـ Footer دائماً في الصف رقم 3 لضمان المحاذاة في كل البطاقات
        footer = CTkFrame(content, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        footer.grid_columnconfigure(0, weight=1)
        
        self.status_dot = CTkLabel(footer, text="●", font=get_font(10), text_color=THEME["text_secondary"])
        self.status_dot.grid(row=0, column=0, sticky="w")
        
        self.status_text = CTkLabel(footer, text="Ready", font=get_font(11), text_color=THEME["text_secondary"])
        self.status_text.grid(row=0, column=0, sticky="w", padx=(15, 0))
        
        launch_btn = CTkButton(
            footer,
            text="▶ Launch",
            width=90,
            height=30,
            fg_color=project["color"],
            hover_color=project["color"],
            text_color="white",
            font=get_font(12, "bold"),
            corner_radius=CONTROL_RADIUS,
            command=self._on_launch
        )
        launch_btn.grid(row=0, column=1, sticky="e")
        
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)
        
    def _on_hover(self, event):
        self.configure(border_color=THEME["accent"], fg_color=THEME["surface_hover"])
        
    def _on_leave(self, event):
        self.configure(border_color=THEME["border"], fg_color=THEME["surface"])
        
    def _on_launch(self):
        self.on_launch(self.project)
        
    def set_status(self, text, color):
        self.status_text.configure(text=text, text_color=color)
        self.status_dot.configure(text_color=color)


class UnifiedLauncher(CTk):
    def __init__(self):
        super().__init__()
        
        self.config = load_config()
        self.log_windows = {}
        self.running_processes = {}
        
        self.title("WE Automation Tools - Unified Launcher")
        self.configure(fg_color=THEME["bg"][0])
        
        ctk.set_appearance_mode(self.config.get("theme", "Light"))
        ctk.set_default_color_theme("dark-blue")
        ctk.set_widget_scaling(1.0)
        
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(1400, max(1100, int(screen_w * 0.85)))
        win_h = min(900, max(750, int(screen_h * 0.85)))
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(950, 650)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        self._build_header()
        self._build_content()
        self._build_footer()
        
        self.after(500, self._check_all_dependencies)
        
    def _build_header(self):
        self.header = CTkFrame(self, fg_color=THEME["surface"], height=70, corner_radius=0, border_width=0)
        self.header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        self.header.grid_propagate(False)
        self.header.grid_columnconfigure(1, weight=1)
        
        # Logo Frame - Pure CTk (No tk.Canvas)
        logo_frame = CTkFrame(self.header, fg_color="transparent", width=60, height=60)
        logo_frame.grid(row=0, column=0, padx=(20, 10), pady=10)
        logo_frame.grid_propagate(False)
        
        try:
            logo_path = BASE_DIR / "assets" / "We_logo.svg.png"
            if logo_path.exists():
                img = Image.open(logo_path).resize((48, 48))
                logo_img = CTkImage(light_image=img, dark_image=img, size=(48, 48))
                CTkLabel(logo_frame, image=logo_img, text="").place(relx=0.5, rely=0.5, anchor="center")
            else:
                raise FileNotFoundError()
        except:
            # Fallback: CTkFrame circle + CTkLabel (No Canvas!)
            logo_circle = CTkFrame(logo_frame, width=48, height=48, corner_radius=24, fg_color=THEME["accent"][0])
            logo_circle.place(relx=0.5, rely=0.5, anchor="center")
            logo_circle.grid_propagate(False)
            CTkLabel(logo_circle, text="WE", text_color="white", font=get_font(14, "bold")).place(relx=0.5, rely=0.5, anchor="center")
        
        title_frame = CTkFrame(self.header, fg_color="transparent")
        title_frame.grid(row=0, column=1, sticky="w", pady=10)
        
        CTkLabel(title_frame, text="Automation Tools", font=get_font(22, "bold"), text_color=THEME["text_primary"]).pack(anchor="w")
        CTkLabel(title_frame, text="Unified Control Panel", font=get_font(13), text_color=THEME["text_secondary"]).pack(anchor="w")
        
        controls = CTkFrame(self.header, fg_color="transparent")
        controls.grid(row=0, column=2, sticky="e", padx=20, pady=10)
        
        self.theme_btn = CTkButton(
            controls,
            text="🌙 Dark" if ctk.get_appearance_mode() == "Light" else "☀️ Light",
            width=100,
            height=34,
            fg_color=THEME["surface_2"],
            hover_color=THEME["surface_hover"],
            text_color=THEME["text_primary"],
            font=get_font(12),
            corner_radius=CONTROL_RADIUS,
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="left", padx=5)
        
        CTkButton(
            controls,
            text="⚙️",
            width=40,
            height=34,
            fg_color=THEME["surface_2"],
            hover_color=THEME["surface_hover"],
            text_color=THEME["text_primary"],
            font=get_font(14),
            corner_radius=CONTROL_RADIUS,
            command=self._open_settings
        ).pack(side="left", padx=5)
        
    def _build_content(self):
        self.scroll_frame = CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=THEME["accent"],
            scrollbar_button_hover_color=THEME["accent_hover"]
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.scroll_frame.grid_columnconfigure((0, 1, 2), weight=1)
        
        header_frame = CTkFrame(self.scroll_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)
        
        CTkLabel(header_frame, text="Available Tools", font=get_font(20, "bold"), text_color=THEME["text_primary"]).grid(row=0, column=0, sticky="w")
        
        self.status_summary = CTkLabel(header_frame, text="Checking dependencies...", font=get_font(12), text_color=THEME["warning"])
        self.status_summary.grid(row=0, column=1, sticky="e")
        
        self.cards = []
        for idx, project in enumerate(PROJECTS):
            card = ProjectCard(
                self.scroll_frame,
                project,
                on_launch=self._launch_project,
                fg_color=THEME["surface"]
            )
            col = idx % 3
            row = (idx // 3) + 1
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            self.cards.append(card)



            
    def _build_footer(self):
        self.footer = CTkFrame(self, fg_color=THEME["surface"], height=40, corner_radius=0)
        self.footer.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        self.footer.grid_propagate(False)
        self.footer.grid_columnconfigure(0, weight=1)
        
        CTkLabel(
            self.footer,
            text=f"📁 Base: {BASE_DIR}  |  💻 Python {sys.version_info.major}.{sys.version_info.minor}  |  Ready",
            font=get_font(11),
            text_color=THEME["text_secondary"]
        ).grid(row=0, column=0, sticky="w", padx=20, pady=10)
        
        self.footer_status = CTkLabel(
            self.footer,
            text="● System Ready",
            font=get_font(11, "bold"),
            text_color=THEME["success"]
        )
        self.footer_status.grid(row=0, column=1, sticky="e", padx=20, pady=10)
        
    def _apply_theme_color(self, color_tuple):
        mode = 0 if ctk.get_appearance_mode() == "Light" else 1
        if isinstance(color_tuple, tuple):
            return color_tuple[mode]
        return color_tuple
        
    def _toggle_theme(self):
        current = ctk.get_appearance_mode()
        new_mode = "Dark" if current == "Light" else "Light"
        ctk.set_appearance_mode(new_mode)
        self.config["theme"] = new_mode
        save_config(self.config)
        
        self.theme_btn.configure(text="☀️ Light" if new_mode == "Dark" else "🌙 Dark")
        self.configure(fg_color=THEME["bg"][1 if new_mode == "Dark" else 0])
        self.header.configure(fg_color=THEME["surface"][1 if new_mode == "Dark" else 0])
        self.footer.configure(fg_color=THEME["surface"][1 if new_mode == "Dark" else 0])
        
    def _check_all_dependencies(self):
        all_ok = True
        missing_map = {}
        
        for card in self.cards:
            project = card.project
            ok, missing = ensure_dependencies(project["requires"])
            if not ok:
                all_ok = False
                missing_map[project["name"]] = missing
                card.set_status(f"Missing: {', '.join(missing)}", THEME["error"])
            else:
                card.set_status("Ready", THEME["success"])
                
        if all_ok:
            self.status_summary.configure(text="All dependencies satisfied", text_color=THEME["success"])
            self.footer_status.configure(text="● All Systems Ready", text_color=THEME["success"])
        else:
            self.status_summary.configure(text=f"Missing deps in {len(missing_map)} tools", text_color=THEME["error"])
            self.footer_status.configure(text="● Dependency Issues", text_color=THEME["warning"])
            self.after(1000, lambda: self._show_deps_dialog(missing_map))
            
    def _show_deps_dialog(self, missing_map):
        dialog = CTkToplevel(self)
        dialog.title("Missing Dependencies")
        dialog.geometry("500x400")
        dialog.configure(fg_color=self._apply_theme_color(THEME["bg"]))
        
        CTkLabel(dialog, text="⚠️ Missing Python Packages", font=get_font(16, "bold"), text_color=THEME["warning"]).pack(pady=(20, 10))
        CTkLabel(dialog, text="Install the following packages to enable all tools:", font=get_font(12), text_color=THEME["text_secondary"]).pack()
        
        textbox = CTkTextbox(dialog, fg_color=THEME["surface_2"], text_color=THEME["text_primary"], font=get_font(12, "normal", "Consolas"))
        textbox.pack(fill="both", expand=True, padx=20, pady=10)
        
        commands = []
        for name, deps in missing_map.items():
            textbox.insert("end", f"• {name}:\n")
            for dep in deps:
                textbox.insert("end", f"  pip install {dep}\n")
                commands.append(dep)
        textbox.configure(state="disabled")
        
        pip_cmd = "pip install " + " ".join(set(commands))
        
        btn_frame = CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        def copy_cmd():
            self.clipboard_clear()
            self.clipboard_append(pip_cmd)
            
        CTkButton(btn_frame, text="📋 Copy pip command", command=copy_cmd, fg_color=THEME["accent"], text_color="white").pack(side="left", padx=5)
        CTkButton(btn_frame, text="Close", command=dialog.destroy, fg_color=THEME["surface_hover"], text_color=THEME["text_primary"]).pack(side="right", padx=5)
        
    def _launch_project(self, project):
        proj_id = project["id"]
        
        if proj_id in self.log_windows and self.log_windows[proj_id].winfo_exists():
            self.log_windows[proj_id].lift()
            self.log_windows[proj_id].focus_force()
            return
            
        log_win = LogWindow(self, project["name"], proj_id)
        self.log_windows[proj_id] = log_win
        log_win.is_running = True
        
        for card in self.cards:
            if card.project["id"] == proj_id:
                card.set_status("Running...", THEME["info"])
                
        thread = threading.Thread(target=self._run_project_thread, args=(project, log_win), daemon=True)
        thread.start()
        
    def _run_project_thread(self, project, log_win):
        try:
            log_win.set_status("Initializing...", THEME["info"])
            log_win.log(f"Starting {project['name']}...", "info")
            log_win.set_progress(0.1)
            
            path = str(project["path"])
            if not os.path.exists(path):
                log_win.log(f"❌ File not found: {path}", "error")
                log_win.set_status("Failed", THEME["error"])
                return
                
            log_win.log(f"Script path: {path}", "info")
            log_win.set_progress(0.3)
            
            if project.get("type") == "cli" and project.get("runner"):
                log_win.log("Loading module...", "info")
                spec = importlib.util.spec_from_file_location(f"tool_{project['id']}", path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                runner_func = getattr(module, project["runner"], None)
                if runner_func:
                    log_win.log("Executing runner function...", "info")
                    log_win.set_progress(0.5)
                    
                    def log_callback(msg):
                        log_win.log(str(msg), "info")
                        log_win.set_progress(min(0.95, log_win.progress.get() + 0.05))
                        
                    try:
                        # unified WO supports passing mode from GUI
                        if project.get("id") == "wo_unified" and hasattr(module, "run_wo_unified"):
                            mode_val = "GPON"
                            # find mode from the card
                            for c in self.cards:
                                if c.project.get("id") == "wo_unified":
                                    if getattr(c, "unified_mode_var", None) is not None:
                                        mode_val = c.unified_mode_var.get()
                                    break

                            runner_func(mode=mode_val, log=log_callback)
                        else:
                            runner_func(log=log_callback)
                    except TypeError:
                        # fallback for runners that don't accept log
                        if project.get("id") == "wo_unified" and hasattr(module, "run_wo_unified"):
                            mode_val = "GPON"
                            for c in self.cards:
                                if c.project.get("id") == "wo_unified":
                                    if getattr(c, "unified_mode_var", None) is not None:
                                        mode_val = c.unified_mode_var.get()
                                    break
                            runner_func(mode=mode_val)
                        else:
                            runner_func()

                        
                    log_win.log("✅ Completed successfully!", "success")
                    log_win.set_status("Done", THEME["success"])
                    log_win.set_progress(1.0)
                else:
                    log_win.log(f"❌ Runner '{project['runner']}' not found", "error")
                    log_win.set_status("Failed", THEME["error"])
            else:
                log_win.log("Launching external process...", "info")
                log_win.set_progress(0.5)
                
                # إجبار العملية الفرعية على استخدام ترميز UTF-8 لتجنب أخطاء UnicodeEncodeError (مثل الرموز التعبيرية)
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"

                proc = subprocess.Popen(
                    [sys.executable, path],
                    cwd=str(project["path"].parent),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env
                )
                self.running_processes[project["id"]] = proc
                
                for line in proc.stdout:
                    if line:
                        log_win.log(line.strip(), "info")
                        
                proc.wait()
                
                if proc.returncode == 0:
                    log_win.log("✅ Process finished successfully", "success")
                    log_win.set_status("Done", THEME["success"])
                else:
                    log_win.log(f"⚠️ Process exited with code {proc.returncode}", "warning")
                    log_win.set_status("Finished", THEME["warning"])
                    
                log_win.set_progress(1.0)
                
        except Exception as e:
            log_win.log(f"❌ Error: {str(e)}", "error")
            log_win.set_status("Error", THEME["error"])
            import traceback
            log_win.log(traceback.format_exc(), "error")
        finally:
            log_win.is_running = False
            for card in self.cards:
                if card.project["id"] == project["id"]:
                    card.set_status("Ready", THEME["success"])
                    
    def _open_settings(self):
        dialog = CTkToplevel(self)
        dialog.title("⚙️ Launcher Settings")
        dialog.geometry("500x300")
        dialog.configure(fg_color=self._apply_theme_color(THEME["bg"]))
        dialog.transient(self)
        dialog.grab_set()
        
        CTkLabel(dialog, text="Launcher Settings", font=get_font(18, "bold"), text_color=THEME["text_primary"]).pack(pady=20)
        
        row = CTkFrame(dialog, fg_color="transparent")
        row.pack(fill="x", padx=30, pady=10)
        CTkLabel(row, text="Appearance:", font=get_font(13), text_color=THEME["text_secondary"]).pack(side="left")
        
        theme_var = ctk.StringVar(value=self.config.get("theme", "Light"))
        CTkOptionMenu(row, values=["Light", "Dark"], variable=theme_var, width=120, 
                     command=lambda x: ctk.set_appearance_mode(x)).pack(side="right")
        
        row2 = CTkFrame(dialog, fg_color="transparent")
        row2.pack(fill="x", padx=30, pady=10)
        CTkLabel(row2, text="UI Scaling:", font=get_font(13), text_color=THEME["text_secondary"]).pack(side="left")
        
        scale_var = ctk.StringVar(value="100%")
        CTkOptionMenu(row2, values=["80%", "90%", "100%", "110%", "120%"], variable=scale_var, width=120, 
                     command=lambda x: ctk.set_widget_scaling(float(x.replace("%", "")) / 100)).pack(side="right")
        
        CTkButton(dialog, text="Save & Close", command=lambda: [save_config({**self.config, "theme": theme_var.get()}), dialog.destroy()], 
                 fg_color=THEME["accent"], text_color="white").pack(pady=20)


def main():
    sys.dont_write_bytecode = True
    
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
            
    app = UnifiedLauncher()
    app.mainloop()


if __name__ == "__main__":
    main()
