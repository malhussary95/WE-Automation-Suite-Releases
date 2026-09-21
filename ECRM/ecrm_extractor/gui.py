# WE ECRM Extractor - Enterprise Professional GUI
# UI redesign matching the approved dashboard concept.
# The existing extraction engine remains in runner.py/dependencies.py.

import os
import json
import time
import threading
import subprocess
import platform
from pathlib import Path
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

try:
    import pandas as pd
except Exception:
    pd = None

from .fields import FIELD_OPTIONS, FIELD_PRESETS
from .web_client import EcrmWebClient


class EcrmApp:
    COLORS = {
        "bg": "#07101F",
        "bg2": "#0B1628",
        "sidebar": "#0D192C",
        "card": "#101E33",
        "card2": "#13243B",
        "border": "#213B5D",
        "text": "#F4F7FB",
        "muted": "#91A4BF",
        "blue": "#1687FF",
        "blue2": "#36A1FF",
        "green": "#28D17C",
        "red": "#EF5B6B",
        "orange": "#F5A623",
        "purple": "#8B5CF6",
    }

    CATEGORIES = {
        "Customer": ["CST Name", "CST Name Arabic", "CST Number", "CST Type", "CST Category", "Branch", "Branch Address", "Account manager", "Account manager mail"],
        "Order": ["Order", "Order Status", "SO Type", "SO Status", "Latest SO", "Current Task"],
        "Network": ["CID", "Circuit Status", "Request Number", "NID", "Speed", "Hardware", "Product", "Transmission Type", "Network Data", "MSAN Data", "POP"],
        "Migration": ["Latest Migration by E-Support SO", "Migration SO Type", "Migration SO Status", "Migration Current Task", "Migration Current Task Owner", "ESPT & infra status", "Notes"],
        "Documents": ["Work Order PDF", "Installed Resources", "ONU Tech Data"],
    }

    def __init__(self, load_credentials, on_start):
        self.load_credentials = load_credentials
        self.on_start = on_start
        self.root = ctk.CTk()
        self.root.title("WE ECRM Extractor — Enterprise Edition")
        self.root.configure(fg_color=self.COLORS["bg"])
        self.root.minsize(1180, 720)
        self.root.geometry(self._center_geometry(1540, 900))
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.file_var = ctk.StringVar()
        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="READY")
        self.mode_var = ctk.StringVar(value="ORDER")
        self.search_var = ctk.StringVar()
        self.debug_var = ctk.BooleanVar(value=False)
        self.max_workers_var = ctk.IntVar(value=5)
        self.direct_values_var = ctk.StringVar()
        self.fields = {f: ctk.BooleanVar(value=False) for f in FIELD_OPTIONS}
        self.field_widgets = {}
        self.cancel_requested = False
        self.is_running = False
        self.progress = None
        self.status_label = None
        self.stat_progress_label = None
        self._partial_results_count = 0
        self._last_progress = 0
        self.output_file = ""
        self.history = self._load_history()
        self.search_history = []
        self.last_results = []
        self.smart_result_callback = self._receive_result
        self.messagebox = messagebox
        self.is_dark = True
        self.web_mode = True
        self.web_client = EcrmWebClient()
        self.web_connected = False

        try:
            u, p = self.load_credentials()
            self.username_var.set(u or "")
            self.password_var.set(p or "")
        except Exception:
            pass

        self._build_shell()
        self._show_dashboard()
        self.root.after(300, self._check_web_connection)

    # ---------------------------- shell ----------------------------
    def _center_geometry(self, w, h):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = min(w, sw - 30); h = min(h, sh - 70)
        return f"{w}x{h}+{max(10,(sw-w)//2)}+{max(10,(sh-h)//2)}"

    def _build_shell(self):
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self.root, width=238, fg_color=self.COLORS["sidebar"], corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.content = ctk.CTkFrame(self.root, fg_color=self.COLORS["bg"], corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=0, minsize=66)
        self.content.grid_rowconfigure(1, weight=0, minsize=58)
        self.content.grid_rowconfigure(2, weight=1)
        self._build_sidebar()
        self._build_topbar()

    def _build_sidebar(self):
        ctk.CTkLabel(self.sidebar, text="WE", text_color=self.COLORS["blue2"],
                     font=ctk.CTkFont(size=36, weight="bold")).pack(anchor="w", padx=25, pady=(24,0))
        ctk.CTkLabel(self.sidebar, text="ECRM Extractor", text_color=self.COLORS["text"],
                     font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=25, pady=(0,2))
        ctk.CTkLabel(self.sidebar, text="Enterprise Edition v2.0", text_color=self.COLORS["muted"],
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=25, pady=(0,28))

        self.nav_buttons = []
        for label, cmd in [
            ("⌂   Dashboard", self._show_dashboard),
            ("ϟ   Extraction", self._show_extraction),
            ("▥   Results", self._show_results),
            ("◷   History", self._show_history),
            ("☆   Presets", self._show_presets),
            ("♙   AI Copilot", self._show_copilot),
            ("⚙   Settings", self._show_settings),
        ]:
            b = ctk.CTkButton(self.sidebar, text=label, command=cmd, anchor="w", height=44,
                              corner_radius=9, fg_color="transparent", hover_color="#142640",
                              text_color=self.COLORS["text"], font=ctk.CTkFont(size=13))
            b.pack(fill="x", padx=12, pady=3)
            self.nav_buttons.append((b, cmd))

        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)
        status = ctk.CTkFrame(self.sidebar, fg_color=self.COLORS["card"], border_width=1,
                              border_color=self.COLORS["border"], corner_radius=12)
        status.pack(fill="x", padx=12, pady=(10,12))
        ctk.CTkLabel(status, text="●  ECRM ONLINE", text_color=self.COLORS["green"],
                     font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=13, pady=(11,2))
        ctk.CTkLabel(status, text="Powered by Automation\nFor a Better Network\n\nv2.0.0", justify="left",
                     text_color=self.COLORS["muted"], font=ctk.CTkFont(size=10)).pack(anchor="w", padx=13, pady=(0,11))

    def _activate_nav(self, command):
        for button, cmd in getattr(self, "nav_buttons", []):
            active = cmd == command
            button.configure(
                fg_color=self.COLORS["blue"] if active else "transparent",
                hover_color=self.COLORS["blue2"] if active else "#142640"
            )

    def _build_topbar(self):
        bar = ctk.CTkFrame(self.content, height=66, fg_color=self.COLORS["bg2"], corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        self.topbar = bar
        bar.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(bar, textvariable=self.search_var, height=38, width=430,
                              placeholder_text="Search in ECRM...  (Ctrl + K)",
                              fg_color=self.COLORS["card"], border_color=self.COLORS["border"],
                              text_color=self.COLORS["text"], placeholder_text_color=self.COLORS["muted"])
        search.grid(row=0, column=0, sticky="w", padx=30, pady=14)
        self.web_status_label = ctk.CTkLabel(bar, text="● WEB CONNECTING", text_color=self.COLORS["orange"],
                     fg_color="#2B2410", corner_radius=12, padx=12, pady=7,
                     font=ctk.CTkFont(size=11, weight="bold"))
        self.web_status_label.grid(row=0,column=1,padx=8)
        ctk.CTkButton(bar, text="WEB", width=48, height=36, fg_color=self.COLORS["card"],
                      hover_color=self.COLORS["card2"], command=self.open_web_ui).grid(row=0,column=2,padx=4)
        ctk.CTkButton(bar, text="☼", width=38, height=36, fg_color=self.COLORS["card"],
                      hover_color=self.COLORS["card2"], command=self.toggle_theme).grid(row=0,column=3,padx=5)
        ctk.CTkButton(bar, text="⚙", width=38, height=36, fg_color=self.COLORS["card"],
                      hover_color=self.COLORS["card2"], command=self._show_settings).grid(row=0,column=4,padx=5)
        ctk.CTkFrame(bar, width=1, height=34, fg_color=self.COLORS["border"]).grid(row=0,column=5,padx=8)
        ctk.CTkLabel(bar, text="MA", width=38, height=38, corner_radius=19, fg_color=self.COLORS["blue"],
                     text_color="white", font=ctk.CTkFont(weight="bold")).grid(row=0,column=6,padx=(4,6))
        ctk.CTkLabel(bar, text="ECRM User\nNetwork Engineer", justify="left", text_color=self.COLORS["text"],
                     font=ctk.CTkFont(size=10)).grid(row=0,column=7,padx=(0,20))

    def _page_header(self, title, subtitle):
        head = ctk.CTkFrame(self.content, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=30, pady=(22,0))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text=title, text_color=self.COLORS["text"],
                     font=ctk.CTkFont(size=25, weight="bold")).grid(row=0,column=0,sticky="w")
        ctk.CTkLabel(head, text=subtitle, text_color=self.COLORS["muted"],
                     font=ctk.CTkFont(size=11)).grid(row=1,column=0,sticky="w",pady=(2,6))

    def _clear_page(self):
        for w in self.content.winfo_children():
            if w is not getattr(self, "topbar", None):
                w.destroy()
        # topbar is row 0 and needs to stay. Rebuild a new header at row 1 by shifting content layout.
        self._build_topbar_if_needed()

    def _build_topbar_if_needed(self):
        # The topbar created in _build_topbar remains. Headers are created at row 1 in page methods.
        pass

    def _header(self, title, subtitle):
        h=ctk.CTkFrame(self.content, fg_color="transparent")
        h.grid(row=1,column=0,sticky="ew",padx=30,pady=(14,0)); h.grid_columnconfigure(0,weight=1)
        ctk.CTkLabel(h,text=title,text_color=self.COLORS["text"],font=ctk.CTkFont(size=25,weight="bold")).grid(row=0,column=0,sticky="w")
        ctk.CTkLabel(h,text=subtitle,text_color=self.COLORS["muted"],font=ctk.CTkFont(size=11)).grid(row=1,column=0,sticky="w",pady=(2,10))

    def _body(self):
        b=ctk.CTkScrollableFrame(self.content,fg_color="transparent",corner_radius=0)
        b.grid(row=2,column=0,sticky="nsew",padx=30,pady=(2,14))
        return b

    def _card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=self.COLORS["card"], border_width=1,
                            border_color=self.COLORS["border"], corner_radius=13, **kwargs)

    def _reset_page(self):
        # Keep only the fixed topbar; row 1 is the compact header and row 2 is expandable.
        for w in list(self.content.winfo_children()):
            if w is not getattr(self, "topbar", None):
                w.destroy()
        self.content.grid_rowconfigure(0, weight=0, minsize=66)
        self.content.grid_rowconfigure(1, weight=0, minsize=58)
        self.content.grid_rowconfigure(2, weight=1, minsize=0)

    def _check_web_connection(self):
        def worker():
            try:
                self.web_client.health()
                self.root.after(0, lambda: self._set_web_status(True))
            except Exception:
                self.root.after(0, lambda: self._set_web_status(False))
        threading.Thread(target=worker, daemon=True).start()

    def _set_web_status(self, connected):
        self.web_connected = bool(connected)
        if getattr(self, "web_status_label", None) and self.web_status_label.winfo_exists():
            if connected:
                self.web_status_label.configure(text="● WEB CONNECTED",
                                                 text_color=self.COLORS["green"],
                                                 fg_color="#0B2B27")
            else:
                self.web_status_label.configure(text="● WEB OFFLINE",
                                                 text_color=self.COLORS["orange"],
                                                 fg_color="#2B2410")

    def web_log(self, message, level="info"):
        if level == "error":
            color = self.COLORS["red"]
        elif level == "warning":
            color = self.COLORS["orange"]
        elif level == "success":
            color = self.COLORS["green"]
        else:
            color = self.COLORS["muted"]
        self._set_status(str(message)[:90], color)

    def web_job_done(self, job):
        status = str(job.get("status", ""))
        output = job.get("output_file") or ""
        self.output_file = output
        self.is_running = False
        if status == "done":
            self.set_progress(100, "COMPLETED")
            self._receive_result([], output, [])
        elif status == "stopped":
            self._set_status("CANCELLED", self.COLORS["orange"])
            self.reset_ui(reset_progress=False)
        else:
            self._set_status("FAILED", self.COLORS["red"])
            self.reset_ui(reset_progress=False)

    def open_web_ui(self):
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000/ecrm")

    def start_web_extraction(self):
        if not self.web_connected:
            self._check_web_connection()
            raise RuntimeError("Web backend is not connected. Start main.py so the bundled Web API is available.")
        self.web_client.run(self)

    # ---------------------------- dashboard ----------------------------
    def _show_dashboard(self):
        self._activate_nav(self._show_dashboard); self._reset_page(); self._header("Good Evening, ECRM User 👋", "Welcome to WE ECRM Extractor — manage your extractions, results and automation from one place.")
        body=self._body();
        for i in range(5): body.grid_columnconfigure(i,weight=1)
        total=len(self.history); success=sum(x.get("status")=="Completed" for x in self.history); failed=sum(x.get("status")=="Failed" for x in self.history); saved=sum(bool(x.get("output")) for x in self.history); today=sum(x.get("date")==datetime.now().strftime("%Y-%m-%d") for x in self.history)
        cards=[("Total Jobs",total,self.COLORS["blue"],"▣","All time extractions"),("Successful",success,self.COLORS["green"],"✓","Completed jobs"),("Failed",failed,self.COLORS["red"],"×","Failed extractions"),("Saved Files",saved,self.COLORS["purple"],"▤","Generated Excel files"),("Today",today,self.COLORS["orange"],"◷","Jobs completed")]
        for i,(t,v,c,ic,sub) in enumerate(cards):
            card=self._card(body); card.grid(row=0,column=i,sticky="nsew",padx=5,pady=6)
            ctk.CTkLabel(card,text=ic,text_color=c,font=ctk.CTkFont(size=22,weight="bold")).pack(anchor="w",padx=15,pady=(13,1))
            ctk.CTkLabel(card,text=t,text_color=self.COLORS["muted"],font=ctk.CTkFont(size=10)).pack(anchor="w",padx=15)
            ctk.CTkLabel(card,text=str(v),text_color=self.COLORS["text"],font=ctk.CTkFont(size=24,weight="bold")).pack(anchor="w",padx=15,pady=(2,0))
            ctk.CTkLabel(card,text=sub,text_color=self.COLORS["muted"],font=ctk.CTkFont(size=9)).pack(anchor="w",padx=15,pady=(0,12))

        quick=self._card(body); quick.grid(row=1,column=0,columnspan=3,sticky="nsew",padx=5,pady=8)
        ctk.CTkLabel(quick,text="ϟ  Quick Extraction",text_color=self.COLORS["text"],font=ctk.CTkFont(size=17,weight="bold")).pack(anchor="w",padx=18,pady=(15,2))
        ctk.CTkLabel(quick,text="Start a new extraction in just a few steps",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18)
        modes=ctk.CTkSegmentedButton(quick,values=["ORDER","CID","SO","ORD"],variable=self.mode_var,selected_color=self.COLORS["blue"],selected_hover_color=self.COLORS["blue2"]); modes.pack(fill="x",padx=18,pady=16)
        row=ctk.CTkFrame(quick,fg_color="transparent"); row.pack(fill="x",padx=18,pady=(0,18));
        ctk.CTkButton(row,text="▣  Choose Excel",height=42,command=self.browse_file).pack(side="left")
        ctk.CTkButton(row,text="Paste Values",height=42,fg_color=self.COLORS["card2"],hover_color="#1B3150",command=self._show_extraction).pack(side="left",padx=8)
        ctk.CTkButton(row,text="START EXTRACTION  →",height=42,fg_color=self.COLORS["blue"],hover_color=self.COLORS["blue2"],command=self._show_extraction).pack(side="right")

        right=self._card(body); right.grid(row=1,column=3,columnspan=2,sticky="nsew",padx=5,pady=8)
        ctk.CTkLabel(right,text="☆  Presets",font=ctk.CTkFont(size=17,weight="bold"),text_color=self.COLORS["text"]).pack(anchor="w",padx=18,pady=(15,2))
        ctk.CTkLabel(right,text="Use predefined field selections",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,8))
        for name in ["Full Report","Technical Check","Customer Profile","Migration Audit"]:
            ctk.CTkButton(right,text=name,anchor="w",height=36,fg_color=self.COLORS["card2"],hover_color="#1B3150",command=lambda n=name:self.apply_preset(n)).pack(fill="x",padx=18,pady=3)

        recent=self._card(body); recent.grid(row=2,column=0,columnspan=3,sticky="nsew",padx=5,pady=8)
        ctk.CTkLabel(recent,text="◷  Recent Jobs",font=ctk.CTkFont(size=16,weight="bold")).pack(anchor="w",padx=18,pady=(15,8))
        if not self.history:
            ctk.CTkLabel(recent,text="No jobs yet. Start your first extraction.",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,18))
        else:
            for x in self.history[-5:][::-1]:
                ctk.CTkLabel(recent,text=f"{x.get('date','')}   {x.get('mode','-')}   {x.get('rows',0)} records   {x.get('status','-')}",text_color=self.COLORS["text"]).pack(anchor="w",padx=18,pady=4)

        ai=self._card(body); ai.grid(row=2,column=3,columnspan=2,sticky="nsew",padx=5,pady=8)
        ctk.CTkLabel(ai,text="♙  AI Copilot",font=ctk.CTkFont(size=16,weight="bold")).pack(anchor="w",padx=18,pady=(15,2))
        ctk.CTkLabel(ai,text="Local Ollama ready for field selection and troubleshooting.",wraplength=350,text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,14))
        ctk.CTkButton(ai,text="Open AI Copilot →",command=self._show_copilot).pack(anchor="w",padx=18,pady=(0,16))

        helpc=self._card(body); helpc.grid(row=3,column=0,columnspan=5,sticky="ew",padx=5,pady=8)
        ctk.CTkLabel(helpc,text="How to get started?",font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=18,pady=(13,2))
        ctk.CTkLabel(helpc,text="1 Choose Mode   →   2 Add Input   →   3 Select Fields   →   4 Start Extraction",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,15))

    # ---------------------------- extraction ----------------------------
    def _show_extraction(self):
        self._activate_nav(self._show_extraction); self._reset_page(); self._header("Extraction", "Build your extraction job, select the required fields and run the existing ECRM engine.")
        body=self._body(); body.grid_columnconfigure(0,weight=3); body.grid_columnconfigure(1,weight=2)
        left=self._card(body); left.grid(row=0,column=0,sticky="nsew",padx=(5,8),pady=5)
        right=self._card(body); right.grid(row=0,column=1,sticky="nsew",padx=(8,5),pady=5)
        ctk.CTkLabel(left,text="1  INPUT",font=ctk.CTkFont(size=17,weight="bold")).pack(anchor="w",padx=18,pady=(16,3))
        ctk.CTkLabel(left,text="Choose ORDER, CID, SO or ORD",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18)
        ctk.CTkSegmentedButton(left,values=["ORDER","CID","SO","ORD"],variable=self.mode_var,selected_color=self.COLORS["blue"],selected_hover_color=self.COLORS["blue2"]).pack(fill="x",padx=18,pady=13)
        drop=ctk.CTkFrame(left,height=155,fg_color=self.COLORS["bg2"],border_width=1,border_color=self.COLORS["blue"],corner_radius=12); drop.pack(fill="x",padx=18,pady=5); drop.pack_propagate(False)
        ctk.CTkLabel(drop,text="☁",font=ctk.CTkFont(size=35),text_color=self.COLORS["blue2"]).pack(pady=(22,0))
        ctk.CTkLabel(drop,text="Drag & Drop Excel File Here",font=ctk.CTkFont(size=14,weight="bold")).pack()
        self.file_label=ctk.CTkLabel(drop,text="or click to browse • .xlsx / .xls",text_color=self.COLORS["muted"]); self.file_label.pack()
        ctk.CTkButton(drop,text="Browse",width=110,height=30,command=self.browse_file).pack(pady=9)
        ctk.CTkLabel(left,text="OR  Paste Values",text_color=self.COLORS["muted"]).pack(pady=(8,3))
        self.direct_input_textbox=ctk.CTkTextbox(left,height=105,fg_color=self.COLORS["bg2"],border_width=1,border_color=self.COLORS["border"]); self.direct_input_textbox.pack(fill="x",padx=18,pady=(0,14)); self.direct_input_textbox.insert("1.0",self.direct_values_var.get())
        ctk.CTkLabel(left,text="Credentials",font=ctk.CTkFont(size=14,weight="bold")).pack(anchor="w",padx=18,pady=(2,4))
        cr=ctk.CTkFrame(left,fg_color="transparent"); cr.pack(fill="x",padx=18,pady=(0,15)); cr.grid_columnconfigure(0,weight=1); cr.grid_columnconfigure(1,weight=1)
        ctk.CTkEntry(cr,textvariable=self.username_var,placeholder_text="ECRM Username").grid(row=0,column=0,sticky="ew",padx=(0,5)); ctk.CTkEntry(cr,textvariable=self.password_var,placeholder_text="Password",show="●").grid(row=0,column=1,sticky="ew",padx=(5,0))

        ctk.CTkLabel(right,text="2  FIELDS",font=ctk.CTkFont(size=17,weight="bold")).pack(anchor="w",padx=18,pady=(16,3))
        ctk.CTkLabel(right,text="Select fields or use a preset",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18)
        toolbar=ctk.CTkFrame(right,fg_color="transparent"); toolbar.pack(fill="x",padx=18,pady=10)
        ctk.CTkButton(toolbar,text="Select All",width=95,height=30,command=self.select_all).pack(side="left"); ctk.CTkButton(toolbar,text="Clear",width=80,height=30,fg_color=self.COLORS["card2"],command=self.clear_all).pack(side="left",padx=6)
        self.selected_count_label=ctk.CTkLabel(toolbar,text="0 selected",text_color=self.COLORS["blue2"]); self.selected_count_label.pack(side="right")
        sf=ctk.CTkScrollableFrame(right,height=360,fg_color=self.COLORS["bg2"]); sf.pack(fill="both",expand=True,padx=18,pady=3)
        for cat, fields in self.CATEGORIES.items():
            ctk.CTkLabel(sf,text=cat.upper(),text_color=self.COLORS["blue2"],font=ctk.CTkFont(size=10,weight="bold")).pack(anchor="w",padx=8,pady=(10,4))
            for field in fields:
                cb=ctk.CTkCheckBox(sf,text=field,variable=self.fields[field],command=self._update_field_count,checkbox_width=17,checkbox_height=17); cb.pack(anchor="w",padx=10,pady=3)
                self.field_widgets[field]=cb
        run=self._card(body); run.grid(row=1,column=0,columnspan=2,sticky="ew",padx=5,pady=8)
        ctk.CTkLabel(run,text="3  RUN",font=ctk.CTkFont(size=17,weight="bold")).pack(anchor="w",padx=18,pady=(14,3))
        worker_row=ctk.CTkFrame(run,fg_color="transparent"); worker_row.pack(fill="x",padx=18,pady=(2,4))
        ctk.CTkLabel(worker_row,text="Parallel Workers",text_color=self.COLORS["muted"]).pack(side="left")
        ctk.CTkOptionMenu(worker_row,values=[str(i) for i in range(1,13)],variable=self.max_workers_var,width=110).pack(side="left",padx=10)
        ctk.CTkLabel(worker_row,text="More workers = faster network I/O, but too many may overload ECRM.",text_color=self.COLORS["muted"]).pack(side="left",padx=8)
        self.progress=ctk.CTkProgressBar(run,height=10); self.progress.set(0); self.progress.pack(fill="x",padx=18,pady=10)
        rr=ctk.CTkFrame(run,fg_color="transparent"); rr.pack(fill="x",padx=18,pady=(0,14)); self.status_label=ctk.CTkLabel(rr,text="READY",text_color=self.COLORS["muted"]); self.status_label.pack(side="left"); self.stat_progress_label=ctk.CTkLabel(rr,text="0%",text_color=self.COLORS["text"]); self.stat_progress_label.pack(side="right")
        ctk.CTkButton(rr,text="🚀  START EXTRACTION",height=42,fg_color=self.COLORS["blue"],hover_color=self.COLORS["blue2"],command=self.start).pack(side="right",padx=(10,0)); self.cancel_btn=ctk.CTkButton(rr,text="Cancel",height=42,fg_color=self.COLORS["card2"],hover_color="#243A58",command=self.cancel); self.cancel_btn.pack(side="right")
        self._update_field_count()

    # ---------------------------- results/history ----------------------------
    def _show_results(self):
        self._activate_nav(self._show_results); self._reset_page(); self._header("Results", "Review the latest output, statistics and generated Excel files.")
        body=self._body(); body.grid_columnconfigure(0,weight=1)
        card=self._card(body); card.grid(row=0,column=0,sticky="ew",pady=5,padx=5)
        if self.output_file:
            ctk.CTkLabel(card,text="Latest Output",font=ctk.CTkFont(size=17,weight="bold")).pack(anchor="w",padx=18,pady=(16,4)); ctk.CTkLabel(card,text=self.output_file,text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,12)); ctk.CTkButton(card,text="Open Folder",command=lambda:self._open_output_folder(self.output_file)).pack(anchor="w",padx=18,pady=(0,16))
        else:
            ctk.CTkLabel(card,text="No result yet",font=ctk.CTkFont(size=17,weight="bold")).pack(anchor="w",padx=18,pady=(16,4)); ctk.CTkLabel(card,text="Run an extraction to generate an Excel result.",text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,16))

    def _show_history(self):
        self._activate_nav(self._show_history); self._reset_page(); self._header("History", "Every completed extraction is recorded locally for quick review.")
        body=self._body()
        if not self.history: ctk.CTkLabel(body,text="No extraction history yet.",text_color=self.COLORS["muted"]).pack(anchor="w",padx=10,pady=20); return
        for x in self.history[::-1]:
            c=self._card(body); c.pack(fill="x",padx=5,pady=5); row=ctk.CTkFrame(c,fg_color="transparent"); row.pack(fill="x",padx=15,pady=12)
            ctk.CTkLabel(row,text=f"{x.get('mode','-')}  •  {x.get('date','-')}",font=ctk.CTkFont(size=14,weight="bold")).pack(side="left")
            ctk.CTkLabel(row,text=f"{x.get('rows',0)} records   |   {x.get('status','-')}",text_color=self.COLORS["muted"]).pack(side="left",padx=25)
            if x.get("output"): ctk.CTkButton(row,text="Open",width=75,command=lambda p=x["output"]:self._open_output_folder(p)).pack(side="right")

    def _show_presets(self):
        self._activate_nav(self._show_presets); self._reset_page(); self._header("Presets", "Reusable field configurations for common ECRM workflows.")
        body=self._body();
        for i,name in enumerate(FIELD_PRESETS):
            c=self._card(body); c.pack(fill="x",padx=5,pady=6); ctk.CTkLabel(c,text=name,font=ctk.CTkFont(size=15,weight="bold")).pack(side="left",padx=18,pady=15); ctk.CTkButton(c,text="Apply →",width=100,command=lambda n=name:self.apply_preset(n)).pack(side="right",padx=15,pady=10)

    def _show_copilot(self):
        self._activate_nav(self._show_copilot); self._reset_page(); self._header("AI Copilot", "Local assistant for field selection, extraction configuration and troubleshooting.")
        body=self._body(); body.grid_columnconfigure(0,weight=1)
        c=self._card(body); c.grid(row=0,column=0,sticky="nsew",padx=5,pady=5)
        ctk.CTkLabel(c,text="Local (Ollama)",text_color=self.COLORS["green"],font=ctk.CTkFont(weight="bold")).pack(anchor="w",padx=20,pady=(18,8))
        ctk.CTkLabel(c,text="Hello 👋\n\nI can help you configure ECRM extraction jobs.\n\n• Field selection\n• Extraction configuration\n• Data analysis\n• Troubleshooting",justify="left",text_color=self.COLORS["text"]).pack(anchor="w",padx=20,pady=5)
        self.ai_entry=ctk.CTkEntry(c,placeholder_text="Type your message..."); self.ai_entry.pack(fill="x",padx=20,pady=20)
        ctk.CTkButton(c,text="Send",command=self._ai_message).pack(anchor="e",padx=20,pady=(0,20))

    def _show_settings(self):
        self._activate_nav(self._show_settings); self._reset_page(); self._header("Settings", "Application, credentials, extraction and local AI preferences.")
        body=self._body(); body.grid_columnconfigure(0,weight=1)
        for title, desc in [("Appearance","Dark enterprise theme is optimized for long extraction sessions."),("ECRM Connection","Credentials are loaded using the existing session manager."),("Extraction","Existing runner supports progress, cancellation and auto-resume."),("AI","Use the local Ollama/Qwen workflow without changing the extraction engine.")]:
            c=self._card(body); c.pack(fill="x",padx=5,pady=6); ctk.CTkLabel(c,text=title,font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=18,pady=(14,2)); ctk.CTkLabel(c,text=desc,text_color=self.COLORS["muted"]).pack(anchor="w",padx=18,pady=(0,14))

    # ---------------------------- actions ----------------------------
    def browse_file(self):
        p=filedialog.askopenfilename(title="Select ECRM input Excel",filetypes=[("Excel files","*.xlsx *.xls"),("All files","*.*")])
        if p:
            self.file_var.set(p)
            if hasattr(self,"file_label"): self.file_label.configure(text=Path(p).name,text_color=self.COLORS["text"])
            self.status_var.set("INPUT READY")

    def select_all(self):
        for v in self.fields.values(): v.set(True)
        self._update_field_count()

    def clear_all(self):
        for v in self.fields.values(): v.set(False)
        self._update_field_count()

    def apply_preset(self,name):
        # Accept both title-case and lower-case preset keys.
        key=name
        if key not in FIELD_PRESETS:
            for k in FIELD_PRESETS:
                if k.lower()==str(name).lower(): key=k; break
        selected=set(FIELD_PRESETS.get(key,[]))
        for f,v in self.fields.items(): v.set(f in selected)
        self._update_field_count()
        self._show_extraction()

    def _update_field_count(self):
        n=sum(v.get() for v in self.fields.values())
        if hasattr(self,"selected_count_label"): self.selected_count_label.configure(text=f"{n} selected")

    @property
    def file_path(self): return self.file_var.get().strip()
    @property
    def direct_values(self):
        if hasattr(self,"direct_input_textbox"):
            raw=self.direct_input_textbox.get("1.0","end").strip()
        else: raw=self.direct_values_var.get().strip()
        return [x.strip() for x in raw.replace(",","\n").splitlines() if x.strip()]
    @property
    def mode(self): return self.mode_var.get()
    @property
    def selected_fields(self): return {f for f,v in self.fields.items() if v.get()}
    @property
    def username(self): return self.username_var.get().strip()
    @property
    def password(self): return self.password_var.get().strip()
    @property
    def debug_mode(self): return bool(self.debug_var.get())
    @property
    def max_workers(self):
        try:
            return max(1, min(int(self.max_workers_var.get()), 12))
        except Exception:
            return 5

    def is_cancelled(self): return self.cancel_requested
    def cancel(self):
        if self.is_running:
            self.cancel_requested=True; self.status_var.set("CANCELLING..."); self._set_status("CANCELLING...",self.COLORS["orange"])
            if self.web_mode:
                self.web_client.stop()

    def reset_ui(self, reset_progress=True):
        self.is_running=False; self.cancel_requested=False
        if reset_progress and self.progress: self.progress.set(0); self._last_progress=0
        if hasattr(self,"cancel_btn"): self.cancel_btn.configure(state="normal")
        self._set_status("READY",self.COLORS["muted"])

    def _set_status(self,text,color=None):
        self.status_var.set(text)
        if self.status_label and self.status_label.winfo_exists(): self.status_label.configure(text=text,text_color=color or self.COLORS["muted"])

    def ask_yes_no(self,title,message): return messagebox.askyesno(title,message,parent=self.root)

    def start(self):
        if self.is_running: return
        if not self.file_path and not self.direct_values:
            messagebox.showwarning("Input Required","Choose an Excel file or paste values.",parent=self.root); return
        if not self.selected_fields:
            messagebox.showwarning("Fields Required","Select at least one field.",parent=self.root); return
        if not self.username or not self.password:
            messagebox.showwarning("Credentials Required","Enter your ECRM username and password.",parent=self.root); return
        self.is_running=True; self.cancel_requested=False; self._partial_results_count=0; self._set_status("STARTING...",self.COLORS["blue2"])
        if self.cancel_btn: self.cancel_btn.configure(state="normal")
        try:
            if self.web_mode:
                self.start_web_extraction()
            else:
                self.on_start(self)
        except Exception as e:
            self.is_running=False; self._set_status("FAILED",self.COLORS["red"]); messagebox.showerror("Start Error",str(e),parent=self.root)

    def set_progress(self,value,status):
        self._last_progress=float(value)
        def update():
            if self.progress: self.progress.set(max(0,min(100,float(value)))/100)
            if self.stat_progress_label and self.stat_progress_label.winfo_exists(): self.stat_progress_label.configure(text=f"{max(0,min(100,float(value))):.0f}%")
            self._set_status(status,self.COLORS["green"] if float(value)>=100 else self.COLORS["blue2"])
        self.root.after(0,update)

    def _receive_result(self,rows,out_excel,headers):
        self.last_results=rows or []; self.output_file=str(out_excel or "")
        self._partial_results_count=len(self.last_results)
        item={"date":datetime.now().strftime("%Y-%m-%d"),"mode":self.mode,"rows":len(self.last_results),"status":"Completed","output":self.output_file}
        self.history.append(item); self._save_history()

    def _open_output_folder(self,path):
        if not path: return
        p=Path(path)
        folder=p if p.is_dir() else p.parent
        try:
            if platform.system()=="Windows": os.startfile(str(folder))
            elif platform.system()=="Darwin": subprocess.Popen(["open",str(folder)])
            else: subprocess.Popen(["xdg-open",str(folder)])
        except Exception: pass

    def _load_history(self):
        try:
            p=Path(__file__).resolve().parents[1]/"output"/".ecrm_gui_history.json"
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return []

    def _save_history(self):
        try:
            p=Path(__file__).resolve().parents[1]/"output"/".ecrm_gui_history.json"; p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(self.history[-100:],ensure_ascii=False,indent=2),encoding="utf-8")
        except Exception: pass

    def _ai_message(self):
        text=self.ai_entry.get().strip()
        if text:
            messagebox.showinfo("AI Copilot","Local Ollama integration point is ready.\n\nYour request:\n"+text,parent=self.root)
            self.ai_entry.delete(0,"end")

    def toggle_theme(self):
        # Keep the approved enterprise dark visual stable; the button acts as a safe no-op for now.
        self.is_dark=True

    def open_smart_chat(self): self._show_copilot()
    def focus_search(self):
        self.search_var.set("")
    def _nav_settings(self): self._show_settings()
    def _nav_history(self): self._show_history()

    def run(self): self.root.mainloop()

    def _on_closing(self):
        self.cancel_requested=True
        try:
            if self.web_mode:
                self.web_client.stop()
        except Exception:
            pass
        try: self._save_history()
        except Exception: pass
        self.root.destroy()
