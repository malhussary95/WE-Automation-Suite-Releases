import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pandas as pd
import os
import json

from PIL import Image, ImageTk

from services.browser import create_driver, login
from core.processor import process_rows
from config import USERNAME, PASSWORD, EXCEL_INPUT, EXCEL_OUTPUT, save_credentials, CREDENTIALS_FILE


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Automation Panel")
        self.root.geometry("800x600")

        BASE_DIR = os.path.dirname(os.path.dirname(__file__))
        self.image_path = os.path.join(BASE_DIR, "assets", "images", "1.png")

        self.action = None
        self.service_type = None
        self.username = USERNAME
        self.password = PASSWORD

        self._show_login_dialog()

    def _show_login_dialog(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                saved_user = data.get("username", "")
                saved_pass = data.get("password", "")
                if saved_user and saved_pass:
                    self.username = saved_user
                    self.password = saved_pass
                    self.create_main_menu()
                    return
            except Exception:
                pass

        self._show_credential_form()

    def _show_credential_form(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.root.configure(bg="white")

        frame = tk.Frame(self.root, bg="white")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(frame, text="Login", bg="white", fg="#800080",
                 font=("Arial", 20, "bold")).pack(pady=(0, 20))

        tk.Label(frame, text="Username:", bg="white", font=("Arial", 12)).pack(anchor="w", padx=20)
        self.login_user_entry = tk.Entry(frame, width=30, font=("Arial", 12))
        self.login_user_entry.pack(padx=20, pady=(0, 10))
        self.login_user_entry.insert(0, self.username)

        tk.Label(frame, text="Password:", bg="white", font=("Arial", 12)).pack(anchor="w", padx=20)
        self.login_pass_entry = tk.Entry(frame, width=30, show="●", font=("Arial", 12))
        self.login_pass_entry.pack(padx=20, pady=(0, 20))
        self.login_pass_entry.insert(0, self.password)

        self.login_error = tk.Label(frame, text="", bg="white", fg="red", font=("Arial", 10))
        self.login_error.pack(pady=(0, 10))

        def on_login():
            user = self.login_user_entry.get().strip()
            pwd = self.login_pass_entry.get().strip()
            if not user or not pwd:
                self.login_error.configure(text="Please enter both username and password")
                return
            self.username = user
            self.password = pwd
            save_credentials(user, pwd)
            self.create_main_menu()

        tk.Button(frame, text="Login", command=on_login, bg="#800080", fg="white",
                  font=("Arial", 12, "bold"), width=15).pack(pady=(0, 10))

        tk.Button(frame, text="Skip", command=self.create_main_menu, bg="gray", fg="white",
                  font=("Arial", 11), width=15).pack()

    def create_main_menu(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # ===== Logo =====
        try:
            img = Image.open(self.image_path).resize((180, 180))
            self.logo = ImageTk.PhotoImage(img)
            self.canvas.create_image(400, 120, image=self.logo)
        except Exception as e:
            print("Image error:", e)

        # ===== Text =====
        user_display = self.username.split("@")[0] if "@" in self.username else self.username
        self.canvas.create_text(400, 250,
                                text=f"Welcome, {user_display}",
                                fill="#800080",
                                font=("Arial", 20, "bold"))

        self.canvas.create_text(400, 290,
                                text="Choose an operation to continue:",
                                fill="#800080",
                                font=("Arial", 14, "bold"))

        # ===== Buttons =====
        btn_validate = tk.Button(
            self.root, text="Validate",
            bg="#800080", fg="white",
            font=("Arial", 14, "bold"),
            width=12,
            command=lambda: self.start_process("validate")
        )

        btn_update = tk.Button(
            self.root, text="Update",
            bg="#800080", fg="white",
            font=("Arial", 14, "bold"),
            width=12,
            command=self.show_update_options
        )

        btn_add = tk.Button(
            self.root, text="Add",
            bg="#009688", fg="white",
            font=("Arial", 14, "bold"),
            width=12,
            command=self.show_add_options
        )

        btn_exit = tk.Button(
            self.root, text="Exit",
            bg="#cc3333", fg="white",
            font=("Arial", 14, "bold"),
            width=12,
            command=self.root.destroy
        )

        btn_creds = tk.Button(
            self.root, text="Credentials",
            bg="#607d8b", fg="white",
            font=("Arial", 14, "bold"),
            width=12,
            command=self._show_credential_form
        )

        # ===== مهم جدًا =====
        self.canvas.create_window(250, 380, window=btn_validate)
        self.canvas.create_window(400, 380, window=btn_update)
        self.canvas.create_window(550, 380, window=btn_add)
        self.canvas.create_window(166, 460, window=btn_creds)
        self.canvas.create_window(400, 460, window=btn_exit)

        # ===== Hover =====
        for btn in [btn_validate, btn_update]:
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#a366cc"))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#800080"))

        btn_add.bind("<Enter>", lambda e: btn_add.config(bg="#33b5aa"))
        btn_add.bind("<Leave>", lambda e: btn_add.config(bg="#009688"))

        btn_exit.bind("<Enter>", lambda e: btn_exit.config(bg="#ff6666"))
        btn_exit.bind("<Leave>", lambda e: btn_exit.config(bg="#cc3333"))

    def show_add_options(self):
        self.show_service_options("add")

    def show_update_options(self):
        self.show_service_options("update")

    def show_service_options(self, action):
        for w in self.root.winfo_children():
            w.destroy()

        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        title = "Select Service Type"
        if action == "update":
            title = "Select Service Type to Update"

        self.canvas.create_text(400, 180,
                                text=title,
                                fill="#800080",
                                font=("Arial", 20, "bold"))

        services = [
            ("WiMax", "#3f51b5", "wimax"),
            ("SHDSL", "#ff9800", "shdsl"),
            ("Fiber", "#009688", "fiber"),
            ("FTTH", "#607d8b", "ftth"),
            ("VDSL", "#795548", "vdsl"),
        ]

        positions = [
            (250, 300), (400, 300), (550, 300),
            (325, 360), (475, 360)
        ]

        for (name, color, value), (x, y) in zip(services, positions):
            btn = tk.Button(
                self.root,
                text=name,
                bg=color,
                fg="white",
                font=("Arial", 13, "bold"),
                width=12,
                command=lambda v=value, a=action: self.start_service(a, v)
            )
            self.canvas.create_window(x, y, window=btn)

        btn_back = tk.Button(
            self.root, text="Back",
            bg="#cc3333", fg="white",
            font=("Arial", 14, "bold"),
            width=15,
            command=self.create_main_menu
        )

        self.canvas.create_window(400, 450, window=btn_back)

    def start_service(self, action, service_type):
        self.action = action
        self.service_type = service_type
        self.selected_fields = []
        self.start_process(self.action)

    def start_add(self, service_type):
        self.start_service("add", service_type)

    def start_fiber_update(self):
        self.start_service("update", "fiber")

    def show_fields_selection(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.canvas = tk.Canvas(self.root, width=800, height=600, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # ===== Title =====
        self.canvas.create_text(400, 100,
                                text="Select Fields to Update",
                                fill="#800080",
                                font=("Arial", 20, "bold"))

        # ===== Fields =====
        self.fields_vars = {}

        fields = [
            "Customer Name", "Customer Number", "MsanIp",
            "Cabinet Name", "POP", "Sector",
            "Zone Name", "Comment", "Circuit ID"
        ]

        frame = tk.Frame(self.root, bg="white")

        # توزيع 3 أعمدة
        for i, field in enumerate(fields):
            var = tk.BooleanVar()

            row = i // 3
            col = i % 3

            chk = tk.Checkbutton(
                frame,
                text=field,
                variable=var,
                bg="white",
                fg="#800080",
                font=("Arial", 12, "bold"),
                anchor="w"
            )

            chk.grid(row=row, column=col, padx=25, pady=8, sticky="w")
            self.fields_vars[field] = var

        # ===== Buttons =====
        btn_start = tk.Button(
            self.root, text="Start Update",
            bg="#800080", fg="white",
            font=("Arial", 14, "bold"),
            width=20,
            command=self.submit_fields
        )

        btn_back = tk.Button(
            self.root, text="Back",
            bg="#cc3333", fg="white",
            font=("Arial", 14, "bold"),
            width=20,
            command=self.create_main_menu
        )

        # ===== Placement =====
        self.canvas.create_window(400, 280, window=frame)
        self.canvas.create_window(400, 460, window=btn_start)
        self.canvas.create_window(400, 520, window=btn_back)

        # ===== Hover Effects =====
        btn_start.bind("<Enter>", lambda e: btn_start.config(bg="#a366cc"))
        btn_start.bind("<Leave>", lambda e: btn_start.config(bg="#800080"))

        btn_back.bind("<Enter>", lambda e: btn_back.config(bg="#ff6666"))
        btn_back.bind("<Leave>", lambda e: btn_back.config(bg="#cc3333"))

    def submit_fields(self):
        self.selected_fields = [f for f, v in self.fields_vars.items() if v.get()]
        self.start_process("update")

    def create_log_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        self.stop_flag = False

        self.progress_var = tk.DoubleVar()

        ttk.Progressbar(self.root, variable=self.progress_var, maximum=100).pack(pady=10)

        self.text = tk.Text(self.root)
        self.text.pack()

        tk.Button(self.root, text="Stop", command=self.stop_process).pack()

    def stop_process(self):
        self.stop_flag = True

    def log(self, msg):
        self.root.after(0, lambda: self.text.insert(tk.END, msg + "\n"))

    def start_process(self, action):
        self.action = action
        if not self.service_type:
            self.service_type = "wimax"

        self.create_log_screen()

        threading.Thread(target=self.run).start()

    def run(self):
        driver = None
        try:
            driver = create_driver()
            login(driver, self.username, self.password)

            sheet_map = {
                "wimax": "WiMax Template",
                "ftth": "FTTH Template",
                "fiber": "Fiber Template",
                "vdsl": "VDSL Template",
                "shdsl": "SHDSL Template"
            }
            sheet_name = sheet_map.get(self.service_type.lower())

            if not sheet_name:
                self.log(f"❌ No sheet configured for {self.service_type}")
                return

         
            try:
                df = pd.read_excel(EXCEL_INPUT, sheet_name=sheet_name)
            except:
                self.log(f"⚠️ Sheet '{sheet_name}' not found, using default")
                df = pd.read_excel(EXCEL_INPUT)

            self.log(f"📄 Using sheet: {sheet_name}")
            self.log(f"📊 Rows: {len(df)}")

            total = len(df)

            def progress(i):
                self.progress_var.set((i / total) * 100)

            process_rows(
                df,
                driver,
                self.action,
                self.service_type,
                self.log,
                getattr(self, "selected_fields", []),
                {
                    "MsanIp": "MSAN IP",
                    "ncs0": "Shelf",
                    "ncc0": "Card",
                    "ncp0": "Port"
                },
                progress,
                lambda: self.stop_flag
            )

            df.to_excel(EXCEL_OUTPUT, index=False)

            self.log("✅ Done")

        finally:
            if driver:
                driver.quit()
