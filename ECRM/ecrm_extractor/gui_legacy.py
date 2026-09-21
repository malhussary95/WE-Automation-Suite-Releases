# =========================================================
# Premium Modern ECRM Extractor UI
# Ultimate Professional Edition - ENHANCED v3.0
# =========================================================

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

import customtkinter as ctk
from tkinter import Menu, filedialog, messagebox
from types import SimpleNamespace
import sys
import hashlib
import re
import time
import tempfile
import threading
import json
import requests
import asyncio
from PIL import Image
from datetime import datetime
from collections import deque

try:
    from tkinterdnd2 import COPY, DND_FILES, DND_TEXT, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("tkinterdnd2 not found. Drag and drop will be disabled.")

# =========================================================
# FIELD_OPTIONS - Updated to match the image exactly
# =========================================================

FIELD_OPTIONS = [
    "Order", "CST Name", "CST Name Arabic", "CST Number", "CST Type",
    "CST Category", "Branch", "Branch Address", "Account manager", "Account manager mail",
    "Order Status", "SO Type", "SO Status", "Latest SO", "Current Task",
    "Latest Migration by E-Support SO", "Migration SO Type", "Migration SO Status", "Migration Current Task", "Migration Current Task Owner",
    "CID", "Circuit Status", "Request Number", "ESPT & infra status", "Notes", "NID",
    "Speed", "Hardware", "Product", "Transmission Type", "Network Data",
    "MSAN Data", "POP", "Work Order PDF", "Installed Resources"
]

FIELD_PRESETS = {
    "full report": FIELD_OPTIONS,
    "technical check": ["Order", "CID", "Speed", "Product", "Transmission Type", "Network Data", "MSAN Data", "POP", "ESPT & infra status", "Order Status"],
    "customer profile": ["Order", "CST Name", "CST Name Arabic", "CST Number", "CST Type", "Branch", "Account manager", "Account manager mail", "CID"],
    "migration audit": ["Order", "Latest Migration by E-Support SO", "Migration SO Type", "Migration SO Status", "Migration Current Task", "Migration Current Task Owner"]
}

# =========================================================
# Toast Notification System
# =========================================================

class ToastManager:
    """نظام إشعارات عائمة غير مزعجة"""
    def __init__(self, parent):
        self.parent = parent
        self.active_toasts = []
        self.max_toasts = 3
        
    def show(self, message, type_="info", duration=3000):
        """عرض إشعار جديد"""
        # إزالة أقدم إشعار إذا وصلنا للحد الأقصى
        if len(self.active_toasts) >= self.max_toasts:
            oldest = self.active_toasts.pop(0)
            try:
                oldest.destroy()
            except:
                pass
                
        toast = ctk.CTkToplevel(self.parent)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.attributes("-alpha", 0)
        
        colors = {
            "success": ("#22c55e", "#dcfce7"),
            "error": ("#ef4444", "#fee2e2"),
            "warning": ("#f59e0b", "#fef3c7"),
            "info": ("#3b82f6", "#dbeafe")
        }
        
        fg, bg = colors.get(type_, colors["info"])
        
        # إطار الإشعار
        frame = ctk.CTkFrame(toast, fg_color=bg, corner_radius=10, border_width=1, border_color=fg)
        frame.pack(padx=2, pady=2)
        
        # أيقونة حسب النوع
        icons = {"success": "✓", "error": "✕", "warning": "!", "info": "ℹ"}
        icon = icons.get(type_, "ℹ")
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 4))
        
        ctk.CTkLabel(header, text=icon, text_color=fg, font=("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkLabel(header, text=type_.upper(), text_color=fg, font=("Segoe UI", 10, "bold")).pack(side="left", padx=(4, 0))
        
        # زر الإغلاق
        close_btn = ctk.CTkLabel(header, text="✕", text_color=fg, font=("Segoe UI", 10), cursor="hand2")
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._close_toast(toast))
        
        # الرسالة
        msg_label = ctk.CTkLabel(frame, text=message, text_color="#374151", font=("Segoe UI", 12), wraplength=280)
        msg_label.pack(padx=12, pady=(0, 10))
        
        # تحديد الموقع
        self._position_toast(toast)
        
        # تأثير الظهور
        self._fade_in(toast)
        
        # جدولة الإغلاق
        toast.after(duration, lambda: self._close_toast(toast))
        
        self.active_toasts.append(toast)
        
    def _position_toast(self, toast):
        """وضع الإشعار في الأسفل يمين الشاشة"""
        toast.update_idletasks()
        width = 320
        height = 80
        
        parent_x = self.parent.winfo_x()
        parent_y = self.parent.winfo_y()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        x = parent_x + parent_width - width - 20
        y = parent_y + parent_height - height - 20 - (len(self.active_toasts) * 90)
        
        toast.geometry(f"{width}x{height}+{x}+{y}")
        
    def _fade_in(self, toast, alpha=0):
        """تأثير الظهور التدريجي"""
        if alpha < 0.95:
            alpha += 0.1
            toast.attributes("-alpha", alpha)
            toast.after(20, lambda: self._fade_in(toast, alpha))
            
    def _close_toast(self, toast):
        """إغلاق الإشعار مع تأثير"""
        def fade_out(alpha=1):
            if alpha > 0:
                alpha -= 0.1
                try:
                    toast.attributes("-alpha", alpha)
                    toast.after(20, lambda: fade_out(alpha))
                except:
                    pass
            else:
                try:
                    if toast in self.active_toasts:
                        self.active_toasts.remove(toast)
                    toast.destroy()
                except:
                    pass
        fade_out()

# =========================================================
# Auto-Save Manager
# =========================================================

class AutoSaveManager:
    """حفظ تلقائي للإعدادات"""
    def __init__(self, app, interval=30000):
        self.app = app
        self.interval = interval
        self.autosave_file = "ecrm_autosave.json"
        self._schedule_save()
        
    def _schedule_save(self):
        self.save_state()
        self.app.root.after(self.interval, self._schedule_save)
        
    def save_state(self):
        state = {
            'timestamp': datetime.now().isoformat(),
            'selected_fields': [f for f, v in self.app.fields.items() if v.get()],
            'mode': self.app.mode_var.get(),
            'theme': 'dark' if self.app.is_dark else 'light',
            'window_geometry': self.app.root.geometry(),
            'username': self.app.username_var.get(),  # مشفر
            'search_history': list(self.app.search_history) if hasattr(self.app, 'search_history') else [],
            'extraction_count': getattr(self.app, 'extraction_count', 0)
        }
        try:
            with open(self.autosave_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Autosave error: {e}")
            
    def restore_state(self):
        try:
            with open(self.autosave_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                return state
        except FileNotFoundError:
            return None

# =========================================================
# Extraction Analytics
# =========================================================

class ExtractionAnalytics:
    """إحصائيات الاستخراج المتقدمة"""
    def __init__(self, max_history=100):
        self.history = deque(maxlen=max_history)
        self.start_time = None
        
    def start_session(self):
        self.start_time = time.time()
        
    def record_extraction(self, mode, fields_count, values_count, success=True):
        duration = time.time() - self.start_time if self.start_time else 0
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'mode': mode,
            'fields': fields_count,
            'values': values_count,
            'duration': duration,
            'success': success
        })
        
    def get_stats(self):
        if not self.history:
            return None
            
        total = len(self.history)
        successful = sum(1 for h in self.history if h['success'])
        avg_duration = sum(h['duration'] for h in self.history) / total
        
        # أكثر الوضعيات استخداماً
        from collections import Counter
        modes = Counter(h['mode'] for h in self.history)
        favorite_mode = modes.most_common(1)[0] if modes else ('N/A', 0)
        
        # متوسط الحقول والقيم
        avg_fields = sum(h['fields'] for h in self.history) / total
        avg_values = sum(h['values'] for h in self.history) / total
        
        return {
            'total': total,
            'success_rate': (successful / total) * 100,
            'avg_duration': avg_duration,
            'favorite_mode': favorite_mode[0],
            'avg_fields': avg_fields,
            'avg_values': avg_values,
            'recent_extractions': list(self.history)[-5:]
        }

# =========================================================
# Shortcut Manager
# =========================================================

class ShortcutManager:
    """إدارة اختصارات لوحة المفاتيح"""
    DEFAULT_SHORTCUTS = {
        'new_extraction': '<Control-n>',
        'save_preset': '<Control-s>',
        'open_chat': '<Control-space>',
        'focus_search': '<Control-f>',
        'toggle_theme': '<Control-t>',
        'cancel': '<Escape>',
        'select_all': '<Control-a>',
        'clear_all': '<Control-Shift-c>',
        'open_settings': '<Control-comma>',
        'open_history': '<Control-h>',
    }
    
    def __init__(self, app):
        self.app = app
        self.shortcuts = self.load_shortcuts()
        self.bind_all()
        
    def load_shortcuts(self):
        try:
            with open('shortcuts.json', 'r') as f:
                return json.load(f)
        except:
            return self.DEFAULT_SHORTCUTS.copy()
            
    def bind_all(self):
        bindings = {
            'new_extraction': self.app.clear_all,
            'open_chat': self.app.open_smart_chat,
            'focus_search': self.app.focus_search,
            'toggle_theme': self.app.toggle_theme,
            'cancel': self.app.cancel,
            'select_all': self.app.select_all,
            'clear_all': self.app.clear_all,
            'open_settings': self.app._nav_settings,
            'open_history': self.app._nav_history,
        }
        
        for action, key in self.shortcuts.items():
            handler = bindings.get(action)
            if handler:
                self.app.root.bind(key, lambda e, h=handler: (h(), "break")[1])

# =========================================================
# Theme Engine
# =========================================================

class ThemeEngine:
    """محرك themes متقدم"""
    THEMES = {
        'purple': {
            'primary': '#5b2d91',
            'secondary': '#7c3aed',
            'accent': '#a855f7',
            'bg': ('#f7f5fb', '#120a20'),
            'surface': ('#ffffff', '#1a1029'),
            'success': '#22c55e',
            'warning': '#f59e0b',
            'error': '#ef4444',
        },
        'ocean': {
            'primary': '#0ea5e9',
            'secondary': '#0284c7',
            'accent': '#38bdf8',
            'bg': ('#f0f9ff', '#0c1929'),
            'surface': ('#ffffff', '#0f172a'),
            'success': '#10b981',
            'warning': '#f59e0b',
            'error': '#ef4444',
        },
        'forest': {
            'primary': '#059669',
            'secondary': '#047857',
            'accent': '#34d399',
            'bg': ('#f0fdf4', '#052e16'),
            'surface': ('#ffffff', '#064e3b'),
            'success': '#22c55e',
            'warning': '#f59e0b',
            'error': '#ef4444',
        },
        'midnight': {
            'primary': '#4f46e5',
            'secondary': '#4338ca',
            'accent': '#818cf8',
            'bg': ('#fafafa', '#0f0f23'),
            'surface': ('#ffffff', '#1a1a2e'),
            'success': '#22c55e',
            'warning': '#f59e0b',
            'error': '#ef4444',
        }
    }
    
    def __init__(self, app):
        self.app = app
        self.current_theme = 'purple'
        
    def apply_theme(self, theme_name):
        theme = self.THEMES.get(theme_name, self.THEMES['purple'])
        self.current_theme = theme_name
        
        # تحديث الألوان الرئيسية
        THEME["bg"] = theme['bg']
        THEME["surface"] = theme['surface']
        THEME["accent"] = (theme['primary'], theme['secondary'])
        THEME["accent_hover"] = (theme['secondary'], theme['primary'])
        THEME["success"] = (theme['success'], theme['success'])
        THEME["warning"] = (theme['warning'], theme['warning'])
        THEME["error"] = (theme['error'], theme['error'])
        
        # تحديث الواجهة
        self.app._refresh_field_styles()
        self.app.toast.show(f"Theme changed to {theme_name.title()}", "success")

# =========================================================
# Context Memory for Smart Chat
# =========================================================

class ContextMemory:
    """ذاكرة سياقية للمحادثات"""
    def __init__(self, max_context=10):
        self.contexts = {}
        self.max_context = max_context
        
    def add_context(self, user_id, message, response, extracted_data=None):
        if user_id not in self.contexts:
            self.contexts[user_id] = []
            
        self.contexts[user_id].append({
            'message': message,
            'response': response,
            'timestamp': time.time(),
            'extracted_data': extracted_data
        })
        
        # الاحتفاظ بآخر سياقات فقط
        if len(self.contexts[user_id]) > self.max_context:
            self.contexts[user_id].pop(0)
            
    def get_relevant_context(self, user_id, current_message, limit=3):
        """استرجاع السياقات ذات الصلة"""
        contexts = self.contexts.get(user_id, [])
        if not contexts:
            return []
            
        # يمكن إضافة logic للـ similarity search هنا
        return contexts[-limit:]
        
    def get_conversation_summary(self, user_id):
        """ملخص المحادثة"""
        contexts = self.contexts.get(user_id, [])
        if not contexts:
            return "No previous context"
            
        return f"Previous {len(contexts)} messages in conversation"

# =========================================================
# Enhanced Smart Chat Engine with Streaming
# =========================================================

class EnhancedSmartChatEngine:
    """محرك Smart Chat محسّن مع Streaming و Context"""
    
    def __init__(self, app):
        self.app = app
        self.history = []
        self.cache = {}
        self.cache_limit = 50
        self.max_history = 10
        self.is_processing = False
        self.context_memory = ContextMemory()
        self.streaming_enabled = True
        
    def build_enhanced_prompt(self, user_input, user_id="default"):
        lang = self.app.detect_chat_language(user_input)
        
        # الحصول على السياق السابق
        context = self.context_memory.get_conversation_summary(user_id)
        
        lang_instructions = {
            "en": "Respond in professional English.",
            "ar_fusha": "Respond in Modern Standard Arabic (الفصحى) with professional tone.",
            "ar_eg_colloquial": "Respond in Egyptian Arabic dialect (العامية المصرية) naturally and warmly."
        }
        
        lang_rule = lang_instructions.get(lang, "Respond in the same language as the user.")
        
        return f"""
        You are 'Smart Assistant', a professional colleague and expert in ECRM systems.
        
        Context: {context}
        
        Technical Context:
        - Available Fields: {", ".join(FIELD_OPTIONS)}
        - Available Modes: ORDER, CID, SO, ORD
        
        Current Input: "{user_input}"
        
        Rules:
        1. {lang_rule}
        2. Be concise but friendly
        3. Return JSON with: mode, fields, values, wants_to_save, friendly_reply
        
        JSON Schema:
        {{
          "mode": "ORDER"|"CID"|"SO"|"ORD"|null,
          "fields": [],
          "values": [],
          "wants_to_save": boolean,
          "friendly_reply": "..."
        }}
        """
        
    def process_streaming(self, user_input, callback, user_id="default"):
        """معالجة مع Streaming للردود"""
        if self.is_processing:
            return False
            
        self.is_processing = True
        
        def stream_thread():
            try:
                payload = {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that returns valid JSON."},
                        {"role": "user", "content": self.build_enhanced_prompt(user_input, user_id)}
                    ],
                    "model": "openai",
                    "stream": True
                }
                
                response = requests.post(self.app.ai_api_url, json=payload, stream=True, timeout=30)
                full_text = ""
                
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith('data: '):
                            try:
                                data = json.loads(decoded[6:])
                                chunk = data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                                if chunk:
                                    full_text += chunk
                                    # تحديث الواجهة في الوقت الفعلي
                                    self.app.root.after(0, lambda t=full_text: callback(t, is_streaming=True))
                            except:
                                pass
                                
                # معالجة النتيجة النهائية
                try:
                    json_match = re.search(r'\{.*\}', full_text, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                        self.app.root.after(0, lambda: callback(result, is_streaming=False))
                except:
                    pass
                    
            except Exception as e:
                self.app.root.after(0, lambda: callback({"error": str(e)}, is_streaming=False))
            finally:
                self.is_processing = False
                
        threading.Thread(target=stream_thread, daemon=True).start()
        return True

# =========================================================
# Fonts
# =========================================================

def get_system_font():
    if sys.platform == "win32":
        return "Segoe UI Variable Text"
    elif sys.platform == "darwin":
        return ".AppleSystemUIFont"
    return "Inter"

MODERN_FONT = get_system_font()
DISPLAY_FONT = "Segoe UI Variable Display" if sys.platform == "win32" else MODERN_FONT
MONO_FONT = "Cascadia Mono" if sys.platform == "win32" else MODERN_FONT

def ui_font(size=13, weight="normal", family=None):
    weights = {"normal": "normal", "bold": "bold", "semibold": "bold"}
    return ctk.CTkFont(
        family=family or MODERN_FONT,
        size=size,
        weight=weights.get(weight, "normal")
    )

def title_font(size=18, weight="bold"):
    return ui_font(size=size, weight=weight, family=DISPLAY_FONT)

def data_font(size=13, weight="normal"):
    return ui_font(size=size, weight=weight, family=MONO_FONT)

# =========================================================
# Theme
# =========================================================

THEME = {
    "bg": ("#f7f5fb", "#120a20"),
    "surface": ("#ffffff", "#1a1029"),
    "surface_2": ("#f9f7fc", "#251537"),
    "surface_hover": ("#f0e9f8", "#34204b"),
    "border": ("#e5e0eb", "#443057"),
    "accent": ("#5b2d91", "#6b35a6"),
    "accent_hover": ("#4a2379", "#5b2d91"),
    "accent_soft": ("#eee4f7", "#332047"),
    "sidebar": ("#2d1b4e", "#1e1233"),
    "sidebar_hover": ("#3d2663", "#2a1a45"),
    "text_primary": ("#171022", "#fbf8ff"),
    "text_secondary": ("#74657f", "#c9bdd6"),
    "text_on_accent": "#ffffff",
    "success": ("#22c55e", "#22c55e"),
    "warning": ("#f59e0b", "#f59e0b"),
    "error": ("#ef4444", "#ef4444"),
    "card_shadow": ("#e8e3ef", "#0d0818"),
}

CARD_RADIUS = 12
CONTROL_RADIUS = 8

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("dark-blue")

# =========================================================
# Custom Dialogs
# =========================================================

class SecurityDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Security Check")
        self.geometry("420x240")
        self.resizable(False, False)
        self.configure(fg_color=THEME["surface"])

        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (420 // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (240 // 2)
        self.geometry(f"+{x}+{y}")

        self.result = None
        self.transient(parent)
        self.grab_set()

        self.label = ctk.CTkLabel(
            self, text="Admin Authentication Required",
            font=title_font(18), text_color=THEME["text_primary"]
        )
        self.label.pack(pady=(35, 10))

        self.password_entry = ctk.CTkEntry(
            self, placeholder_text="Enter Security Code",
            show="●", width=300, height=45,
            fg_color=THEME["surface_2"], border_color=THEME["border"],
            font=ui_font(14)
        )
        self.password_entry.pack(pady=10)
        self.password_entry.focus()

        self.ok_btn = ctk.CTkButton(
            self, text="Unlock Debug Mode", width=300, height=45,
            fg_color=THEME["accent"], hover_color=THEME["accent_hover"],
            font=ui_font(14, "semibold"), command=self._on_submit
        )
        self.ok_btn.pack(pady=(15, 20))

        self.bind("<Return>", lambda e: self._on_submit())
        self.bind("<Escape>", lambda e: self.destroy())

    def _on_submit(self):
        self.result = self.password_entry.get()
        self.destroy()

    def get_input(self):
        self.master.wait_window(self)
        return self.result

# =========================================================
# Smart Chat Engine (الأصلي + المحسّن)
# =========================================================

class SmartChatEngine:
    """Enhanced Smart Chat engine with memory and cache"""

    def __init__(self, app):
        self.app = app
        self.history = []
        self.cache = {}
        self.cache_limit = 50
        self.max_history = 10
        self.is_processing = False

    def add_to_history(self, role, content):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_cache_key(self, text):
        return hashlib.md5(text.lower().strip().encode()).hexdigest()[:16]

    def get_cached_response(self, text):
        key = self.get_cache_key(text)
        return self.cache.get(key)

    def cache_response(self, text, response):
        if len(self.cache) >= self.cache_limit:
            self.cache.pop(next(iter(self.cache)))
        key = self.get_cache_key(text)
        self.cache[key] = response

    def build_prompt(self, user_input):
        lang = self.app.detect_chat_language(user_input)

        lang_instructions = {
            "en": "Respond in professional English.",
            "ar_fusha": "Respond in Modern Standard Arabic (الفصحى) with professional tone.",
            "ar_eg_colloquial": "Respond in Egyptian Arabic dialect (العامية المصرية) naturally and warmly."
        }

        lang_rule = lang_instructions.get(lang, "Respond in the same language as the user.")

        context = ""
        if self.history:
            context = "\nPrevious Conversation Context:\n"
            for msg in self.history[-6:]:
                prefix = "User" if msg["role"] == "user" else "Assistant"
                context += f"{prefix}: {msg['content']}\n"

        return f"""
        You are 'Smart Assistant', a professional colleague and expert in ECRM systems.
        Your goal is to chat with the user and assist them in extracting data intelligently.

        Technical Context:
        - Available Fields: {", ".join(FIELD_OPTIONS)}
        - Available Modes: ORDER, CID, SO, ORD

        {context}

        Current User Input: "{user_input}"

        Mandatory Rules:
        1. {lang_rule}
        2. If the input is a greeting, respond with a warm and professional greeting in the detected language.
        3. Do not assume numbers or fields exist if they are not explicitly mentioned.
        4. Set "wants_to_save" to true immediately without asking if both
           (Order/CID number) and (Data Fields) are identified.
           Keywords like "save, extract, get, start" and Arabic equivalents
           (استخرج, احفظ, ابدأ, هات, عايز) mean start immediately.
        5. Return the response as a JSON object ONLY, with no surrounding text.
           Place your friendly response in the "friendly_reply" field.

        JSON Schema:
        {{
          "mode": "ORDER" or "CID" or "SO" or "ORD" or null,
          "fields": [], "values": [], "wants_to_save": boolean,
          "friendly_reply": "Your friendly response here"
        }}
        """

    def process(self, user_input, callback, lang_hint=None):
        if self.is_processing:
            return False

        cached = self.get_cached_response(user_input)
        if cached:
            callback(cached, from_cache=True)
            return True

        self.is_processing = True
        self.add_to_history("user", user_input)

        threading.Thread(
            target=self._call_ai,
            args=(user_input, callback, lang_hint),
            daemon=True
        ).start()
        return True

    def _call_ai(self, user_input, callback, lang_hint=None):
        self.app.ai_last_cancel_id += 1
        my_id = self.app.ai_last_cancel_id

        if lang_hint is None:
            lang_hint = self.app.detect_chat_language(user_input)

        clean_input = user_input.strip().lower()
        if len(clean_input) < 60:
            local_parsed = self.app._parse_smart_request(user_input)
            if local_parsed["values"] and local_parsed["fields"]:
                self.add_to_history("assistant", "Processing locally for speed...")
                self.app.root.after(0, lambda: self.app._append_smart_chat(
                    "Smart Assistant", "⚡ Detected locally — applying settings..."
                ))
                self.app.root.after(50, lambda: self.app.apply_smart_request(
                    user_input, from_chat=True
                ))
                self.is_processing = False
                return

        is_greeting = False
        if lang_hint in ("ar_fusha", "ar_eg_colloquial"):
            for g in self.app._greeting_patterns["ar"]:
                if g in clean_input:
                    is_greeting = True
                    break
        else:
            for g in self.app._greeting_patterns["en"]:
                if g in clean_input:
                    is_greeting = True
                    break

        if is_greeting:
            if lang_hint == "ar_eg_colloquial":
                reply = "أهلاً بيك! أنا مساعدك الذكي. عايز تستخرج إيه النهاردة؟"
            elif lang_hint == "ar_fusha":
                reply = "أهلاً وسهلاً! ما البيانات التي ترغب في استخراجها اليوم؟"
            else:
                reply = "Hello! I'm your Smart Assistant. What data would you like to extract today?"

            data = {
                "mode": None, "fields": [], "values": [],
                "wants_to_save": False,
                "friendly_reply": reply
            }
            self.add_to_history("assistant", reply)
            self.app.root.after(0, lambda: self.app._apply_ai_result(data))
            self.is_processing = False
            return

        lang_names = {
            "en": "English",
            "ar_fusha": "Modern Standard Arabic",
            "ar_eg_colloquial": "Egyptian Arabic dialect"
        }

        prompt = self.build_prompt(user_input)

        payload = {
            "messages": [
                {"role": "system", "content": f"You are a helpful assistant that speaks {lang_names.get(lang_hint, 'the user language')} and returns valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "model": "openai",
            "jsonMode": True
        }

        last_error = None

        for attempt in range(1, self.app.ai_max_retries + 1):
            if my_id != self.app.ai_last_cancel_id:
                self.is_processing = False
                return

            try:
                if attempt > 1:
                    self.app.root.after(0, lambda a=attempt:
                        self.app._append_smart_chat(
                            "Smart Assistant", f"⏳ Attempt {a}..."
                        )
                    )

                response = requests.post(
                    self.app.ai_api_url,
                    json=payload,
                    timeout=self.app.ai_timeout
                )
                response.raise_for_status()
                raw_text = response.text

                if not raw_text:
                    raise ValueError("Empty response")

                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    data = {
                        "mode": None, "fields": [], "values": [],
                        "wants_to_save": False,
                        "friendly_reply": raw_text.strip()
                    }

                valid_modes = {"ORDER", "CID", "SO", "ORD"}
                if data.get("mode") and data["mode"].upper() not in valid_modes:
                    data["mode"] = None
                elif data.get("mode"):
                    data["mode"] = data["mode"].upper()

                self.cache_response(user_input, data)
                self.add_to_history("assistant", data.get("friendly_reply", ""))

                if my_id == self.app.ai_last_cancel_id:
                    self.app.root.after(0, lambda: callback(data, from_cache=False))

                self.is_processing = False
                return

            except requests.exceptions.ReadTimeout:
                last_error = "timeout"
                time.sleep(self.app.ai_retry_delay * attempt)
            except requests.exceptions.ConnectionError:
                last_error = "connection"
                time.sleep(self.app.ai_retry_delay * attempt)
            except Exception as e:
                last_error = str(e)
                time.sleep(1)

        if my_id == self.app.ai_last_cancel_id:
            if lang_hint in ("ar_fusha", "ar_eg_colloquial"):
                friendly_err = "الخدمة الذكية بطيئة حالياً. هستخدم المحرك المحلي..."
            else:
                friendly_err = "AI service is slow. Switching to local engine..."

            fallback_data = {
                "mode": None, "fields": [], "values": [],
                "wants_to_save": False,
                "friendly_reply": friendly_err
            }
            self.app.root.after(0, lambda: callback(fallback_data, from_cache=False))
            self.app.root.after(0, lambda: self.app.apply_smart_request(
                user_input, from_chat=True
            ))

        self.is_processing = False

# =========================================================
# Main Application - ENHANCED
# =========================================================

class EcrmApp:

    def __init__(self, load_credentials, on_start):

        self.load_credentials = load_credentials
        self.on_start = on_start
        self.is_dark = False
        
        # ===== NEW: Initialize Managers =====
        self.toast = None  # سيتم إنشاؤه بعد بناء الـ root
        self.analytics = ExtractionAnalytics()
        self.theme_engine = ThemeEngine(self)
        self.search_history = deque(maxlen=10)
        self.extraction_count = 0

        # =====================================================
        # Root
        # =====================================================
        self.root = ctk.CTk()

        if HAS_DND:
            try:
                TkinterDnD._require(self.root)
                self.root.HAS_DND_INTERNAL = True
            except Exception as e:
                print(f"DnD initialization failed: {e}")
                self.root.HAS_DND_INTERNAL = False
        else:
            self.root.HAS_DND_INTERNAL = False

        self.root.title("ECRM Extractor Premium")
        self.root.configure(fg_color=THEME["bg"])

        try:
            self.root.iconbitmap("icon.ico")
        except Exception:
            pass

        # =====================================================
        # Window
        # =====================================================
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        width = min(1540, max(1320, sw - 40), sw - 40)
        height = min(960, max(840, sh - 40), sh - 40)

        x = max(20, (sw // 2) - (width // 2))
        y = max(20, (sh // 2) - (height // 2))

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min(1280, sw - 40), min(720, sh - 40))

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # ===== NEW: Initialize Toast Manager =====
        self.toast = ToastManager(self.root)

        # =====================================================
        # Vars
        # =====================================================
        self.file_var = ctk.StringVar()
        self.username_var = ctk.StringVar()
        self.password_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="● READY")
        self.status_color_var = ctk.StringVar(value="success")
        self.mode_var = ctk.StringVar(value="ORDER")
        self.debug_var = ctk.BooleanVar(value=False)
        self.search_var = ctk.StringVar()

        self.fields = {}
        self.field_widgets = {}
        self.mode_buttons = {}

        self.progress = None
        self.start_btn = None
        self.status_label = None
        self.count_label = None
        self.fields_frame = None
        self.search_entry = None
        self.empty_search_label = None
        self.direct_input_textbox = None
        self.direct_count_label = None
        self.smart_chat_window = None
        self.smart_chat_log = None
        self.smart_chat_entry = None
        self.typing_indicator = None
        self.debug_checkbox = None
        self.smart_hint_label = None

        self.is_running = False
        self.cancel_requested = False
        self.logo_image = None

        self._direct_count_timer = None
        self._loading_animation_id = None
        self._progress_animation_id = None

        # =====================================================
        # AI Configuration
        # =====================================================
        self.ai_enabled = False
        self._setup_ai()

        # =====================================================
        # Load Credentials
        # =====================================================
        # Load BOTH username and password from credentials.json.
        # No hardcoded/default username (such as admin) is used.
        saved_user, saved_pass = self.load_credentials()
        self.username_var.set(saved_user or "")
        self.password_var.set(saved_pass or "")

        # =====================================================
        # Build
        # =====================================================
        self._build_layout()
        self._set_mode("ORDER")

        # =====================================================
        # NEW: Initialize AutoSave & Shortcuts
        # =====================================================
        self.autosave = AutoSaveManager(self)
        self.shortcuts = ShortcutManager(self)
        
        # استعادة الحالة المحفوظة
        self._restore_autosave()

        # =====================================================
        # Shortcuts
        # =====================================================
        self.root.bind("<Control-o>", lambda e: self.browse_file())
        self.root.bind("<Control-Return>", lambda e: self.start())

    def _restore_autosave(self):
        """استعادة الحالة المحفوظة تلقائياً"""
        state = self.autosave.restore_state()
        if state:
            # استعادة الوضع
            if 'mode' in state:
                self._set_mode(state['mode'])
                
            # استعادة الحقول المختارة
            if 'selected_fields' in state:
                for field in state['selected_fields']:
                    if field in self.fields:
                        self.fields[field].set(True)
                self._update_count()
                
            # استعادة الثيم
            if state.get('theme') == 'dark':
                self.toggle_theme()
                
            self.toast.show("Previous session restored", "success")

    def _on_closing(self):
        """Clean shutdown — stop threads and close properly."""
        self.cancel_requested = True
        
        # حفظ الحالة النهائية
        if hasattr(self, 'autosave'):
            self.autosave.save_state()

        if self._loading_animation_id:
            try:
                self.root.after_cancel(self._loading_animation_id)
            except Exception:
                pass
        if self._progress_animation_id:
            try:
                self.root.after_cancel(self._progress_animation_id)
            except Exception:
                pass

        if self.smart_chat_window and self.smart_chat_window.winfo_exists():
            self.smart_chat_window.destroy()

        self.root.destroy()

    def _setup_ai(self):
        self.ai_enabled = True

        self.ai_api_url = "https://text.pollinations.ai/"
        self.ai_api_key = ""
        self.tts_api_url = "https://api.openai.com/v1/audio/speech"

        self.ai_timeout = 15
        self.ai_max_retries = 2
        self.ai_retry_delay = 2
        self.ai_last_cancel_id = 0

        self.is_speaking = False
        self.voice_enabled = True

        try:
            import pygame
            pygame.mixer.init()
        except Exception:
            pass

        self._eg_colloquial_markers = {
            "تمام", "حاضر", "ازيك", "ازيكوا", "ازيكو", "اهلا", "هتعمل",
            "عايز", "عايزة", "عايزين", "عايزك", "ممكن", "بص", "تسمحلي",
            "تسمحيلي", "حبيبي", "حبيبتي", "يا باشا", "يا فندم", "يا دكتور",
            "ايه", "امتى", "دلوقتي", "كده", "بجد", "غلط", "مش", "صح",
            "تمام اوي", "هات", "هاتلي", "جبت", "عملت", "هنعمل", "يلا",
            "فاضل", "خلاص", "بسرعه", "بطيء", "شوية", "كويس", "وحش",
            "جميل", "شكرا", "ميرسي", "عفوا", "اسف", "اسفة", "مش مشكلة",
            "ان شاء الله", "يا ريت", "لو سمحت", "من فضلك", "على راحتك",
            "ماشي", "طيب", "اوك", "اوكي", "يسطا", "باشا", "باشمهندس",
            "دكتور", "استاذ", "حج", "حجة", "بنت", "ولد", "شباب", "بنات"
        }

        self._greeting_patterns = {
            "ar": ["هلا", "مرحبا", "سلام", "اهلا", "ازيك", "ازيكوا",
                   "صباح الخير", "مساء الخير", "صباح النور", "مساء النور",
                   "السلام عليكم", "وعليكم السلام"],
            "en": ["hello", "hi", "hey", "good morning", "good evening",
                   "welcome", "greetings"]
        }

    def detect_chat_language(self, text: str) -> str:
        if not text or not text.strip():
            return "en"

        t = text.strip()
        latin_letters = len(re.findall(r"[A-Za-z]", t))
        arabic_letters = len(re.findall(r"[\u0600-\u06FF]", t))
        total_chars = len(re.findall(r"[A-Za-z\u0600-\u06FF]", t))

        if total_chars == 0:
            return "en"

        if latin_letters > arabic_letters:
            return "en"

        norm = self._normalize_smart_text(t)

        eg_patterns = [
            r"\b(عايز|عايزة|عايزين|هتعمل|هنعمل|هات|هاتلي|جبت|عملت|دلوقتي|كده|بجد|مش|تمام|حاضر|يلا|ماشي|طيب)\b",
            r"\b(ازيك|ازيكوا|ازيكو|ايه|امتى|فين|ازاي|ليه|مين)\b",
            r"\b(شوية|كويس|وحش|جميل|فاضل|خلاص|بسرعه|على راحتك)\b",
            r"\b(يسطا|باشا|باشمهندس|حج|حجة)\b"
        ]

        for pattern in eg_patterns:
            if re.search(pattern, norm):
                return "ar_eg_colloquial"

        for marker in self._eg_colloquial_markers:
            if marker in norm:
                return "ar_eg_colloquial"

        return "ar_fusha"

    # =========================================================
    # Context
    # =========================================================

    @property
    def context(self):
        return SimpleNamespace(
            file_path=self.file_var.get(),
            direct_values=self._get_direct_values(),
            mode=self.mode_var.get(),
            selected_fields={name for name, value in self.fields.items() if value.get()},
            username=self.username_var.get(),
            password=self.password_var.get(),
            debug_mode=self.debug_var.get(),
            progress=self.progress,
            status_var=self.status_var,
            root=self.root,
            reset_ui=self.reset_ui,
            ask_yes_no=self.ask_yes_no,
            is_cancelled=self.is_cancelled,
            smart_result_callback=self.publish_smart_result,
            messagebox=messagebox,
            toast=self.toast,  # NEW
            analytics=self.analytics  # NEW
        )

    # =========================================================
    # Run
    # =========================================================

    def run(self):
        self.root.mainloop()

    # =========================================================
    # Helpers
    # =========================================================

    def _card(self, parent, fg_color=None, border_width=1):
        return ctk.CTkFrame(
            parent,
            fg_color=fg_color or THEME["surface"],
            border_width=border_width,
            border_color=THEME["border"],
            corner_radius=CARD_RADIUS
        )

    def _section_title(self, parent, title, subtitle=None):
        ctk.CTkLabel(
            parent, text=title,
            text_color=THEME["text_primary"],
            font=title_font(17, "bold")
        ).pack(anchor="w")

        if subtitle:
            self._label(parent, subtitle, size=12).pack(anchor="w", pady=(2, 14))

    def _entry(self, parent, variable, placeholder, show=None, height=42):
        entry = ctk.CTkEntry(
            parent, textvariable=variable,
            placeholder_text=placeholder, show=show, height=height,
            corner_radius=CONTROL_RADIUS, border_width=1,
            border_color=THEME["border"], 
            fg_color=THEME["surface_2"],
            text_color=THEME["text_primary"],
            placeholder_text_color=THEME["text_secondary"],
            font=ui_font(12, "semibold")
        )
        self._attach_context_menu(entry)
        return entry

    def _attach_context_menu(self, widget):
        menu = Menu(widget, tearoff=0)
        menu.add_command(label="Cut", command=lambda: self._context_action(widget, "cut"))
        menu.add_command(label="Copy", command=lambda: self._context_action(widget, "copy"))
        menu.add_command(label="Paste", command=lambda: self._context_action(widget, "paste"))
        menu.add_separator()
        menu.add_command(label="Select All", command=lambda: self._context_action(widget, "select_all"))

        def show_menu(event):
            widget.focus_set()
            menu.tk_popup(event.x_root, event.y_root)
            menu.grab_release()
            return "break"

        widget.bind("<Button-3>", show_menu)
        widget.bind("<Button-2>", show_menu)
        self._bind_text_shortcuts(widget, widget)

        native = self._get_native_widget(widget)
        if native is not widget:
            native.bind("<Button-3>", show_menu)
            native.bind("<Button-2>", show_menu)
            self._bind_text_shortcuts(native, widget)

    def _bind_text_shortcuts(self, bind_target, widget):
        shortcuts = {
            "<Control-a>": "select_all", "<Control-A>": "select_all",
            "<Control-c>": "copy", "<Control-C>": "copy",
            "<Control-v>": "paste", "<Control-V>": "paste",
            "<Control-x>": "cut", "<Control-X>": "cut",
        }
        for sequence, action in shortcuts.items():
            bind_target.bind(
                sequence,
                lambda event, a=action, w=widget: self._context_action(w, a)
            )
        bind_target.bind(
            "<Control-KeyPress>",
            lambda event, w=widget: self._physical_shortcut_action(event, w),
            add="+"
        )

    def _physical_shortcut_action(self, event, widget):
        action_by_keycode = {
            65: "select_all", 67: "copy",
            86: "paste", 88: "cut",
        }
        action = action_by_keycode.get(getattr(event, "keycode", None))
        if not action:
            return None
        return self._context_action(widget, action)

    def _context_action(self, widget, action):
        native = self._get_native_widget(widget)
        native.focus_set()

        if action == "select_all":
            self._select_all_text(widget)
            return "break"

        if action == "copy":
            self._copy_selection(native)
        elif action == "cut":
            self._copy_selection(native)
            self._delete_selection(native)
        elif action == "paste":
            self._paste_clipboard(native)

        if action in {"cut", "paste"}:
            self._schedule_direct_count_update()
        return "break"

    def _select_all_text(self, widget):
        native = self._get_native_widget(widget)
        native.focus_set()
        try:
            native.tag_add("sel", "1.0", "end-1c")
            native.mark_set("insert", "end-1c")
            native.see("insert")
            return
        except Exception:
            pass
        try:
            native.selection_range(0, "end")
            native.icursor("end")
            return
        except Exception:
            pass
        try:
            widget.select_range(0, "end")
            widget.icursor("end")
        except Exception:
            pass

    def _selection_text(self, native):
        try:
            return native.get("sel.first", "sel.last")
        except Exception:
            pass
        try:
            return native.selection_get()
        except Exception:
            return ""

    def _copy_selection(self, native):
        text = self._selection_text(native)
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _delete_selection(self, native):
        try:
            native.delete("sel.first", "sel.last")
            return
        except Exception:
            pass
        try:
            native.delete(native.index("sel.first"), native.index("sel.last"))
        except Exception:
            pass

    def _paste_clipboard(self, native):
        try:
            text = self.root.clipboard_get()
        except Exception:
            return
        self._delete_selection(native)
        try:
            native.insert("insert", text)
            return
        except Exception:
            pass
        try:
            native.insert(native.index("insert"), text)
        except Exception:
            pass

    def _label(self, parent, text, size=12, bold=False, text_color=None):
        return ctk.CTkLabel(
            parent, text=text,
            text_color=text_color or THEME["text_secondary"],
            font=ui_font(size, "bold" if bold else "normal")
        )

    def _outline_button(self, parent, text, command, width=140, height=38, fg_color=None, hover_color=None, text_color=None, border_color=None):
        return ctk.CTkButton(
            parent, text=text, command=command,
            width=width, height=height,
            corner_radius=CONTROL_RADIUS,
            fg_color=fg_color or THEME["surface_hover"],
            hover_color=hover_color or THEME["surface_2"],
            border_width=1, border_color=border_color or THEME["border"],
            text_color=text_color or THEME["text_primary"],
            cursor="hand2", font=ui_font(12, "semibold")
        )

    def _primary_button(self, parent, text, command, width=220, height=46, fg_color=None, hover_color=None):
        return ctk.CTkButton(
            parent, text=text, command=command,
            width=width, height=height,
            corner_radius=CONTROL_RADIUS,
            fg_color=fg_color or THEME["accent"],
            hover_color=hover_color or THEME["accent_hover"],
            border_width=0, text_color="white",
            cursor="hand2", font=ui_font(14, "semibold")
        )

    # =========================================================
    # Layout - New v2.0 Sidebar + Dashboard Layout
    # =========================================================

    def _build_layout(self):
        # Main container: Sidebar + Content
        self.root.grid_columnconfigure(0, weight=0)   # Sidebar fixed
        self.root.grid_columnconfigure(1, weight=1)   # Content expands
        self.root.grid_rowconfigure(0, weight=1)

        # ---- Sidebar ----
        self._build_sidebar()

        # ---- Main Content ----
        content = ctk.CTkFrame(self.root, fg_color=THEME["bg"], corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)  # Fields area expands

        # Header
        self._build_header(content)

        # Separator
        sep = ctk.CTkFrame(content, height=1, fg_color=THEME["border"])
        sep.pack(fill="x", pady=(16, 16))

        # Top row: Credentials + Input Source
        top_row = ctk.CTkFrame(content, fg_color="transparent")
        top_row.pack(fill="x")
        top_row.grid_columnconfigure(0, weight=3) # 30% Space
        top_row.grid_columnconfigure(1, weight=7) # 70% Space

        self._build_credentials(top_row)
        self._build_input_source(top_row)

        # Middle: Quick Actions + Data Fields
        mid_row = ctk.CTkFrame(content, fg_color="transparent")
        mid_row.pack(fill="both", expand=True, pady=(16, 0))
        mid_row.grid_columnconfigure(0, weight=0, minsize=220)  # Quick Actions fixed width
        mid_row.grid_columnconfigure(1, weight=1)                # Data Fields expand
        mid_row.grid_rowconfigure(0, weight=1)

        self._build_quick_actions(mid_row)
        self._build_fields_section(mid_row)

        # Footer / Status Bar
        self._build_footer(content)

    # =========================================================
    # Sidebar
    # =========================================================

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self.root,
            fg_color=THEME["sidebar"],
            corner_radius=0,
            width=210
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(6, weight=1)  # Push bottom section down
        sidebar.grid_propagate(False)

        # Logo area
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(30, 20))

        # Logo circle
        logo_circle = ctk.CTkFrame(
            logo_frame, width=50, height=50,
            corner_radius=25, fg_color=THEME["accent"]
        )
        logo_circle.pack(pady=(0, 10))
        logo_circle.pack_propagate(False)
        ctk.CTkLabel(
            logo_circle, text="we", text_color="white",
            font=title_font(18, "bold")
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            logo_frame, text="WE ECRM",
            text_color="white", font=title_font(16, "bold")
        ).pack()
        ctk.CTkLabel(
            logo_frame, text="Extractor Premium",
            text_color="#a890c0", font=ui_font(11)
        ).pack()

        # Nav items with Unicode icons (matching image)
        nav_configs = [
            ("🏠", "Dashboard", self._nav_dashboard),
            ("💬", "Smart Chat", self.open_smart_chat),
            ("🕐", "Extraction History", self._nav_history),
            ("⭐", "Presets", self._nav_presets),
            ("⚙️", "Settings", self._nav_settings),
            ("📊", "Analytics", self._show_analytics),  # NEW
        ]

        for icon_name, label, cmd in nav_configs:
            btn = ctk.CTkButton(
                sidebar, text=f"  {icon_name}  {label}",
                anchor="w", height=42, corner_radius=8,
                fg_color="transparent", hover_color=THEME["sidebar_hover"],
                text_color="white", font=ui_font(13, "semibold"),
                command=cmd
            )
            btn.pack(fill="x", padx=12, pady=4)

        # Spacer pushes bottom content
        # Status box
        status_box = ctk.CTkFrame(
            sidebar, fg_color="#1e1233", corner_radius=10,
            border_width=1, border_color="#3d2663"
        )
        status_box.pack(fill="x", padx=16, pady=(20, 10))

        self.sidebar_status_dot = ctk.CTkLabel(
            status_box, text="●", text_color=THEME["success"],
            font=ui_font(12, "bold")
        )
        self.sidebar_status_dot.pack(side="left", padx=(12, 4), pady=10)

        self.sidebar_status_text = ctk.CTkLabel(
            status_box, text="READY",
            text_color="white", font=ui_font(12, "bold")
        )
        self.sidebar_status_text.pack(side="left", pady=10)

        self.sidebar_status_sub = ctk.CTkLabel(
            status_box, text="System is ready\nto extract data",
            text_color="#a890c0", font=ui_font(10)
        )
        self.sidebar_status_sub.pack(anchor="w", padx=12, pady=(0, 10))

        # User info
        user_box = ctk.CTkFrame(
            sidebar, fg_color="#1e1233", corner_radius=10,
            border_width=1, border_color="#3d2663"
        )
        user_box.pack(fill="x", padx=16, pady=(0, 10))

        user_icon = ctk.CTkFrame(
            user_box, width=32, height=32, corner_radius=16,
            fg_color="#4a3b6b"
        )
        user_icon.pack(side="left", padx=(12, 8), pady=10)
        user_icon.pack_propagate(False)
        ctk.CTkLabel(
            user_box, text="M", text_color="white",
            font=ui_font(14, "bold")
        ).place(in_=user_icon, relx=0.5, rely=0.5, anchor="center")

        user_text = ctk.CTkFrame(user_box, fg_color="transparent")
        user_text.pack(side="left", pady=10)
        ctk.CTkLabel(
            user_text, text="Mahmoud Al-Hussary",
            text_color="white", font=ui_font(12, "semibold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            user_text, text="Owner",
            text_color="#a890c0", font=ui_font(10)
        ).pack(anchor="w")

        # Version
        ctk.CTkLabel(
            sidebar, text="🛡 Version 3.0.0",
            text_color="#a890c0", font=ui_font(10)
        ).pack(side="bottom", pady=(10, 20))

    def _nav_dashboard(self):
        self.toast.show("Dashboard is already active", "info")

    def _nav_history(self):
        """فتح مجلد التاريخ الذي يحتوي على ملفات الإكسيل المستخرجة."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_folder = os.path.join(base_dir, "output")
        
        if os.path.exists(output_folder):
            import platform
            import subprocess
            path = os.path.abspath(output_folder)
            try:
                if platform.system() == "Windows":
                    os.startfile(path)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
                self.toast.show("Opening history folder...", "success")
            except Exception as e:
                self.toast.show(f"Error: {e}", "error")
        else:
            self.toast.show("No extraction history found yet", "warning")

    def _nav_presets(self):
        """فتح نافذة لاختيار وتطبيق أنماط الحقول الجاهزة."""
        preset_window = ctk.CTkToplevel(self.root)
        preset_window.title("Field Presets")
        preset_window.geometry("420x400")
        preset_window.attributes("-topmost", True)
        preset_window.configure(fg_color=THEME["surface"])

        ctk.CTkLabel(
            preset_window, text="Select Field Preset", 
            font=title_font(18), text_color=THEME["text_primary"]
        ).pack(pady=(25, 15))

        for name in FIELD_PRESETS.keys():
            btn = ctk.CTkButton(
                preset_window, 
                text=name.replace("_", " ").title(),
                command=lambda n=name: [self.apply_preset(n), preset_window.destroy(), self.toast.show(f"Applied {n} preset", "success")],
                height=45, width=300,
                corner_radius=CONTROL_RADIUS,
                fg_color=THEME["accent"],
                hover_color=THEME["accent_hover"],
                font=ui_font(14, "semibold")
            )
            btn.pack(pady=8)

        ctk.CTkLabel(
            preset_window, text="Note: Applying a preset resets current selections.",
            text_color=THEME["text_secondary"], font=ui_font(11)
        ).pack(pady=(15, 0))

    def _nav_settings(self):
        """فتح نافذة إعدادات التطبيق العامة."""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x400")
        settings_window.attributes("-topmost", True)
        settings_window.configure(fg_color=THEME["surface"])

        ctk.CTkLabel(
            settings_window, text="Application Settings", 
            font=title_font(18), text_color=THEME["text_primary"]
        ).pack(pady=(25, 20))

        # خيار تبديل المظهر
        theme_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        theme_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(theme_frame, text="Appearance Mode:", font=ui_font(14, "semibold")).pack(side="left")
        
        theme_btn = ctk.CTkSegmentedButton(
            theme_frame, 
            values=["Light", "Dark"],
            command=lambda v: [ctk.set_appearance_mode(v), setattr(self, 'is_dark', v == "Dark")],
            selected_color=THEME["accent"],
            selected_hover_color=THEME["accent_hover"]
        )
        theme_btn.set("Dark" if self.is_dark else "Light")
        theme_btn.pack(side="right")

        # ===== NEW: Theme Selector =====
        color_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        color_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(color_frame, text="Color Theme:", font=ui_font(14, "semibold")).pack(side="left")
        
        themes = ["purple", "ocean", "forest", "midnight"]
        theme_menu = ctk.CTkOptionMenu(
            color_frame, 
            values=[t.title() for t in themes],
            command=lambda v: self.theme_engine.apply_theme(v.lower()),
            width=150
        )
        theme_menu.pack(side="right")

        # خيار وضع التصحيح
        debug_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        debug_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(debug_frame, text="Debug Mode:", font=ui_font(14, "semibold")).pack(side="left")
        
        debug_sw = ctk.CTkSwitch(
            debug_frame, text="", variable=self.debug_var, 
            onvalue=True, offvalue=False, progress_color=THEME["accent"]
        )
        debug_sw.pack(side="right")

        # Auto-save info
        autosave_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        autosave_frame.pack(fill="x", padx=40, pady=10)
        ctk.CTkLabel(autosave_frame, text="Auto-Save:", font=ui_font(14, "semibold")).pack(side="left")
        ctk.CTkLabel(autosave_frame, text="Enabled (30s interval)", text_color=THEME["success"], font=ui_font(12)).pack(side="right")

        ctk.CTkLabel(
            settings_window, 
            text=f"Version: 3.0.0 Premium Edition\nSystem: {sys.platform}",
            text_color=THEME["text_secondary"],
            font=ui_font(10)
        ).pack(side="bottom", pady=20)

    def _show_analytics(self):
        """عرض نافذة الإحصائيات"""
        stats = self.analytics.get_stats()
        
        analytics_window = ctk.CTkToplevel(self.root)
        analytics_window.title("Extraction Analytics")
        analytics_window.geometry("500x400")
        analytics_window.configure(fg_color=THEME["surface"])
        
        ctk.CTkLabel(
            analytics_window, 
            text="📊 Extraction Analytics",
            font=title_font(20), text_color=THEME["text_primary"]
        ).pack(pady=(25, 20))
        
        if stats:
            # إحصائيات رئيسية
            stats_frame = ctk.CTkFrame(analytics_window, fg_color="transparent")
            stats_frame.pack(fill="x", padx=30, pady=10)
            
            metrics = [
                ("Total Extractions", str(stats['total'])),
                ("Success Rate", f"{stats['success_rate']:.1f}%"),
                ("Favorite Mode", stats['favorite_mode']),
                ("Avg Duration", f"{stats['avg_duration']:.1f}s"),
                ("Avg Fields", f"{stats['avg_fields']:.1f}"),
            ]
            
            for label, value in metrics:
                row = ctk.CTkFrame(stats_frame, fg_color="transparent")
                row.pack(fill="x", pady=4)
                ctk.CTkLabel(row, text=label, font=ui_font(13)).pack(side="left")
                ctk.CTkLabel(row, text=value, font=ui_font(13, "bold"), text_color=THEME["accent"]).pack(side="right")
        else:
            ctk.CTkLabel(
                analytics_window,
                text="No extraction data available yet.\nStart extracting to see analytics!",
                text_color=THEME["text_secondary"],
                font=ui_font(13)
            ).pack(pady=50)

    # =========================================================
    # Header
    # =========================================================

    def _build_header(self, parent):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x")

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left, text="WE ECRM Extractor",
            text_color=THEME["text_primary"],
            font=title_font(26, "bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            left, text="Professional ECRM Data Extraction Tool",
            text_color=THEME["text_secondary"],
            font=ui_font(13)
        ).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")

        # Theme toggle
        self.theme_btn = self._outline_button(
            right, "☀ Theme", self.toggle_theme, width=100, height=38,
            fg_color=THEME["surface_2"]
        )
        self.theme_btn.pack(side="right", padx=(0, 10))

        # Mode badge
        ctk.CTkLabel(
            right, text="⚡ Order, CID, SO, ORD",
            text_color=THEME["accent"],
            fg_color=THEME["accent_soft"],
            corner_radius=CONTROL_RADIUS,
            width=160, height=34,
            font=ui_font(12, "semibold")
        ).pack(side="right", padx=(0, 10))

        # Debug toggle
        self.debug_checkbox = ctk.CTkCheckBox(
            right, text="Debug",
            variable=self.debug_var,
            command=self._on_debug_toggle,
            checkbox_width=18, checkbox_height=18,
            corner_radius=6,
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            text_color=THEME["text_secondary"],
            font=ui_font(12)
        )
        self.debug_checkbox.pack(side="right", padx=(10, 0))

    # =========================================================
    # Credentials
    # =========================================================

    def _build_credentials(self, parent):
        card = self._card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=18)

        # Header with icon
        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            header, text="👤 Credentials",
            text_color=THEME["text_primary"],
            font=title_font(16, "bold")
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="Saved locally for the current workstation",
            text_color=THEME["text_secondary"], font=ui_font(11)
        ).pack(side="left", padx=(10, 0))

        self._label(inner, "Username", bold=True).pack(anchor="w", pady=(5, 2))
        self._entry(inner, self.username_var, "Username").pack(fill="x", pady=(0, 12))

        self._label(inner, "Password", bold=True).pack(anchor="w", pady=(0, 2))
        self._entry(inner, self.password_var, "Password", show="●").pack(fill="x")

    # =========================================================
    # Input Source
    # =========================================================

    def _build_input_source(self, parent):
        card = self._card(parent)
        card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=18)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            header, text="📥 Input Source",
            text_color=THEME["text_primary"],
            font=title_font(16, "bold")
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="Choose input method and provide values",
            text_color=THEME["text_secondary"], font=ui_font(11)
        ).pack(side="left", padx=(10, 0))

        # Mode buttons
        mode_frame = ctk.CTkFrame(inner, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(0, 14))
        for i in range(4):
            mode_frame.columnconfigure(i, weight=1)

        modes = [("Order", "ORDER"), ("CID", "CID"), ("SO", "SO"), ("ORD", "ORD")]
        for index, (text, value) in enumerate(modes):
            btn = ctk.CTkButton(
                mode_frame, text=text,
                command=lambda v=value: self._set_mode(v),
                height=34, corner_radius=CONTROL_RADIUS,
                border_width=1, cursor="hand2",
                font=ui_font(12, "semibold")
            )
            btn.grid(row=0, column=index, sticky="ew", padx=4)
            self.mode_buttons[value] = btn

        # File path
        file_frame = ctk.CTkFrame(inner, fg_color="transparent")
        file_frame.pack(fill="x")
        file_frame.columnconfigure(0, weight=1)

        self.file_entry = self._entry(
            file_frame, self.file_var, "No file selected"
        )
        self.file_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        if HAS_DND and getattr(self.root, "HAS_DND_INTERNAL", False):
            try:
                self._register_drop_target(self.file_entry, self._on_file_drop, DND_FILES)
            except Exception:
                pass

        self._outline_button(
            file_frame, "Browse", self.browse_file, width=110, height=42
        ).grid(row=0, column=1)

        # Direct input
        direct_frame = ctk.CTkFrame(inner, fg_color="transparent")
        direct_frame.pack(fill="both", expand=True, pady=(14, 0))

        direct_header = ctk.CTkFrame(direct_frame, fg_color="transparent")
        direct_header.pack(fill="x", pady=(0, 6))

        self._label(direct_header, "📋 Paste / Drag Values").pack(side="left")

        self._outline_button(
            direct_header, "Clear", self.clear_direct_input,
            width=70, height=30
        ).pack(side="right")

        self.direct_count_label = ctk.CTkLabel(
            direct_header, text="0 added",
            text_color=THEME["accent"],
            fg_color=THEME["accent_soft"],
            corner_radius=CONTROL_RADIUS,
            width=76, height=28,
            font=ui_font(12, "semibold")
        )
        self.direct_count_label.pack(side="right", padx=(0, 10))

        self.direct_input_textbox = ctk.CTkTextbox(
            direct_frame, height=100,
            corner_radius=CONTROL_RADIUS,
            border_width=1, border_color=THEME["border"],
            fg_color=THEME["surface_2"],
            text_color=THEME["text_primary"],
            font=data_font(14), wrap="word"
        )
        self.direct_input_textbox.pack(fill="both", expand=True)
        self.direct_input_textbox.insert("1.0", self._direct_placeholder_text())
        self.direct_input_textbox.configure(text_color=THEME["text_secondary"])
        self.direct_input_textbox.bind("<FocusIn>", self._clear_direct_placeholder)
        self.direct_input_textbox.bind("<FocusOut>", self._restore_direct_placeholder)
        self.direct_input_textbox.bind("<KeyRelease>", self._schedule_direct_count_update)
        self.direct_input_textbox.bind("<<Paste>>", self._schedule_direct_count_update)
        self._attach_context_menu(self.direct_input_textbox)

        if HAS_DND and getattr(self.root, "HAS_DND_INTERNAL", False):
            try:
                self._register_drop_target(
                    self.direct_input_textbox, self._on_direct_drop, DND_TEXT
                )
            except Exception:
                pass

    # =========================================================
    # Quick Actions
    # =========================================================

    def _build_quick_actions(self, parent):
        card = self._card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=(0, 0))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            inner, text="⚡ Quick Actions",
            text_color=THEME["text_primary"],
            font=title_font(16, "bold")
        ).pack(anchor="w", pady=(0, 16))

        # Start Extraction
        self.start_btn = ctk.CTkButton(
            inner, text="Start Extraction\nExtract data to Excel",
            compound="top",
            command=self.start,
            height=70, corner_radius=CONTROL_RADIUS,
            fg_color=THEME["accent"], hover_color=THEME["accent_hover"],
            text_color="white", cursor="hand2",
            font=ui_font(15, "bold")
        )
        self.start_btn.pack(fill="x", pady=(0, 10))

        # Cancel button
        self.cancel_btn = ctk.CTkButton(
            inner, text="🚫 Cancel",
            command=self.cancel,
            height=40, corner_radius=CONTROL_RADIUS,
            fg_color="#fef2f2", hover_color="#fee2e2",
            border_width=1, border_color="#fecaca",
            text_color=THEME["error"], cursor="hand2",
            font=ui_font(13, "semibold")
        )
        self.cancel_btn.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            inner, text="Stop current extraction",
            text_color=THEME["text_secondary"], font=ui_font(11)
        ).pack(anchor="center", pady=(0, 16))

        # Clear All
        clear_btn = ctk.CTkButton(
            inner, text="🧹 Clear All",
            command=self.clear_all,
            height=40, corner_radius=CONTROL_RADIUS,
            fg_color=THEME["surface_2"], hover_color=THEME["surface_hover"],
            border_width=1, border_color=THEME["border"],
            text_color=THEME["text_primary"], cursor="hand2",
            font=ui_font(13, "semibold")
        )
        clear_btn.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            inner, text="Reset all selections",
            text_color=THEME["text_secondary"], font=ui_font(11)
        ).pack(anchor="center", pady=(0, 0))

    # =========================================================
    # Fields - FIXED: 5 columns to match image exactly
    # =========================================================

    def _build_fields_section(self, parent):
        card = self._card(parent)
        card.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=(0, 0))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=18, pady=18)

        # Top bar
        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, 12))

        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left")

        ctk.CTkLabel(
            left, text="📊 Data Fields",
            text_color=THEME["text_primary"],
            font=title_font(18, "bold")
        ).pack(side="left")

        self.count_label = ctk.CTkLabel(
            left, text="0 selected",
            text_color=THEME["accent"],
            font=ui_font(12, "semibold")
        )
        self.count_label.pack(side="left", padx=(14, 0))

        self._outline_button(
            left, "Select All", self.select_all,
            width=90, height=28
        ).pack(side="left", padx=(14, 4))

        self._outline_button(
            left, "Clear All", self.clear_all,
            width=90, height=28
        ).pack(side="left", padx=(4, 0))

        search_container = ctk.CTkFrame(
            top, fg_color=THEME["surface_2"], 
            corner_radius=10, border_width=1, 
            border_color=THEME["border"]
        )
        search_container.pack(side="right")
        
        search_icon_label = ctk.CTkLabel(search_container, text="🔍", font=ui_font(14))
        search_icon_label.pack(side="left", padx=(10, 0))

        self.search_var.trace_add("write", self.filter_fields)
        self.search_entry = self._entry(
            search_container, self.search_var, "Search fields...", height=36
        )
        self.search_entry.configure(
            width=220, 
            border_width=0, 
            fg_color=THEME["surface_2"]
        )
        self.search_entry.pack(side="right")

        # Fields grid container - 5 columns as per image
        self.fields_frame = ctk.CTkScrollableFrame(
            inner, fg_color=THEME["surface"],
            border_width=0, corner_radius=CARD_RADIUS,
        )
        self.fields_frame.pack(fill="both", expand=True)

        columns = 6 # 6 columns as requested in point 6
        for i in range(columns):
            self.fields_frame.columnconfigure(i, weight=1)

        for index, field_name in enumerate(FIELD_OPTIONS):
            var = ctk.BooleanVar(value=False)
            self.fields[field_name] = var

            row = index // columns
            col = index % columns

            cell = ctk.CTkFrame(
                self.fields_frame,
                fg_color=THEME["surface_2"],
                corner_radius=6,
                height=32
            )
            cell.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            cell.grid_propagate(False)
            self._add_cell_hover(cell, field_name)

            checkbox = ctk.CTkCheckBox(
                cell, text="", variable=var,
                checkbox_width=18, checkbox_height=18,
                corner_radius=6, fg_color=THEME["accent"],
                hover_color=THEME["accent_hover"],
                command=lambda n=field_name: self._on_field_toggle(n)
            )
            checkbox.place(relx=0.05, rely=0.5, anchor="w")

            label = ctk.CTkLabel(
                cell, text=field_name, anchor="w",
                justify="left",
                cursor="hand2", text_color=THEME["text_primary"],
                font=ui_font(10, "semibold"),
                wraplength=140
            )
            label.place(relx=0.25, rely=0.5, anchor="w")
            label.bind("<Button-1>", lambda e, n=field_name: self._on_field_click(n))

            self.field_widgets[field_name] = (cell, checkbox, label)

    # =========================================================
    # Hover
    # =========================================================

    def _add_cell_hover(self, cell, field_name):
        def on_enter():
            if not self.fields[field_name].get():
                cell.configure(fg_color=THEME["accent_soft"])

        def on_leave():
            if not self.fields[field_name].get():
                cell.configure(fg_color=THEME["surface_2"])

        cell.bind("<Enter>", lambda e: on_enter())
        cell.bind("<Leave>", lambda e: on_leave())

    # =========================================================
    # Footer
    # =========================================================

    def _build_footer(self, parent):
        footer = ctk.CTkFrame(
            parent, fg_color=THEME["surface"],
            border_width=1, border_color=THEME["border"],
            corner_radius=CARD_RADIUS
        )
        footer.pack(side="bottom", fill="x", pady=(16, 0))

        # Progress bar
        bottom = ctk.CTkFrame(footer, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=10)

        # Left: Status
        status_left = ctk.CTkFrame(bottom, fg_color="transparent")
        status_left.pack(side="left")

        # Moved progress bar inside status card area implicitly or as card
        self.progress = ctk.CTkProgressBar(
            status_left, height=6, width=180, corner_radius=100,
            progress_color=THEME["accent"],
            fg_color=THEME["border"]
        )
        self.progress.pack(side="bottom", pady=(5, 0))
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(
            status_left, textvariable=self.status_var,
            text_color=THEME["success"][1],
            font=ui_font(12, "semibold")
        )
        self.status_label.pack(side="left")

        ctk.CTkLabel(
            status_left, text="System is ready to extract data",
            text_color=THEME["text_secondary"], font=ui_font(11)
        ).pack(side="left", padx=(10, 0))

        stats_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        stats_frame.pack(side="right", padx=(0, 20))

        self.stat_values_label = self._create_stat_card(stats_frame, "Values", "0")
        self.stat_fields_label = self._create_stat_card(stats_frame, "Fields", "0", color=THEME["accent"])
        self.stat_progress_label = self._create_stat_card(stats_frame, "Progress", "0%")

    def _create_stat_card(self, parent, title, initial_value, color=None):
        card = ctk.CTkFrame(parent, fg_color=THEME["surface_2"], corner_radius=8, border_width=1, border_color=THEME["border"], width=85, height=48)
        card.pack(side="left", padx=6)
        card.pack_propagate(False)

        val_label = ctk.CTkLabel(
            card, text=initial_value,
            text_color=color or THEME["text_primary"], font=ui_font(13, "bold")
        )
        val_label.pack(pady=(4, 0))

        ctk.CTkLabel(
            card, text=title,
            text_color=THEME["text_secondary"], font=ui_font(9)
        ).pack()
        
        return val_label

    # =========================================================
    # Debug Toggle
    # =========================================================

    def _on_debug_toggle(self):
        if self.debug_var.get():
            self.debug_var.set(False)

            dialog = SecurityDialog(self.root)
            password = dialog.get_input()

            if password:
                table = str.maketrans(
                    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
                    "01234567890123456789"
                )
                cleaned = str(password).strip().translate(table)

                if cleaned == "401095":
                    self.debug_var.set(True)
                    self.root.update_idletasks()
                    self.toast.show("Debug mode activated", "success")
                else:
                    self.toast.show("Access Denied: Incorrect Password", "error")
                    self.debug_checkbox.deselect()

    # =========================================================
    # Mode
    # =========================================================

    def _set_mode(self, value):
        old_placeholder = self._direct_placeholder_text()
        self.mode_var.set(value)

        for v, btn in self.mode_buttons.items():
            if v == value:
                btn.configure(
                    fg_color=THEME["accent"],
                    border_color=THEME["accent"],
                    text_color="white"
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    border_color=THEME["border"],
                    text_color=THEME["text_secondary"]
                )

        self._refresh_direct_placeholder(old_placeholder)

    # =========================================================
    # Field
    # =========================================================

    def _on_field_click(self, field_name):
        var = self.fields[field_name]
        var.set(not var.get())
        self._update_field_style(field_name)
        self._update_count_label()

    def _update_field_style(self, field_name):
        if field_name not in self.field_widgets:
            return
        cell, checkbox, label = self.field_widgets[field_name]
        active = self.fields[field_name].get()

        if active:
            cell.configure(fg_color=THEME["accent_soft"])
            label.configure(text_color=THEME["accent"], font=ui_font(11, "bold"))
        else:
            cell.configure(fg_color=THEME["surface_2"])
            label.configure(
                text_color=THEME["text_primary"],
                font=ui_font(11, "semibold")
            )

    def _refresh_field_styles(self):
        for field_name in self.field_widgets:
            self._update_field_style(field_name)

    def _on_field_toggle(self, field_name):
        self._update_field_style(field_name)
        self._update_count_label()

    def _update_count_label(self):
        count = sum(1 for v in self.fields.values() if v.get())
        self.count_label.configure(text=f"{count} selected")
        self.stat_fields_label.configure(text=str(count))

    def apply_preset(self, preset_name):
        target_fields = FIELD_PRESETS.get(preset_name, [])
        for var in self.fields.values():
            var.set(False)
        for field in target_fields:
            if field in self.fields:
                self.fields[field].set(True)
        self._update_count()

    def _update_count(self):
        self._update_count_label()
        self._refresh_field_styles()

    # =========================================================
    # Status
    # =========================================================

    def _update_status_color(self):
        color_key = self.status_color_var.get()
        color = THEME.get(color_key, THEME["text_secondary"])
        if isinstance(color, tuple):
            color = color[1] if self.is_dark else color[0]
        if self.status_label:
            self.status_label.configure(text_color=color)

    # =========================================================
    # Progress Animation
    # =========================================================

    def _start_processing_animation(self):
        """Single combined animation for processing state."""
        self._anim_tick = 0

        def animate():
            if not self.is_running:
                return

            dots = "." * (self._anim_tick % 4)
            self.status_var.set(f"● PROCESSING{dots}")

            self._anim_tick += 1
            self._progress_animation_id = self.root.after(100, animate)

        animate()

    def _stop_processing_animation(self):
        """Stop any running animations."""
        if self._progress_animation_id:
            try:
                self.root.after_cancel(self._progress_animation_id)
            except Exception:
                pass
            self._progress_animation_id = None

    # =========================================================
    # Search
    # =========================================================

    def focus_search(self):
        if self.search_entry:
            self.search_entry.focus()
            self.search_entry.select_range(0, "end")

    def filter_fields(self, *args):
        text = self.search_var.get().lower().strip()
        
        # NEW: إضافة للـ search history
        if text and text not in self.search_history:
            self.search_history.append(text)
        
        visible_count = 0

        for field_name, widgets in self.field_widgets.items():
            cell, checkbox, label = widgets
            if not text or text in field_name.lower():
                cell.grid()
                visible_count += 1
            else:
                cell.grid_remove()

        if visible_count == 0:
            if not self.empty_search_label:
                self.empty_search_label = ctk.CTkLabel(
                    self.fields_frame, text="No matching fields found",
                    text_color=THEME["text_secondary"], font=ui_font(14)
                )
                self.empty_search_label.grid(
                    row=100, column=0, columnspan=5, pady=40
                )
        else:
            if self.empty_search_label:
                self.empty_search_label.destroy()
                self.empty_search_label = None

    # =========================================================
    # File
    # =========================================================

    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if file_path:
            self.file_var.set(file_path)
            self.toast.show(f"File selected: {os.path.basename(file_path)}", "success")

    def _get_native_widget(self, widget):
        for attr in ("_entry", "_textbox", "_text"):
            if hasattr(widget, attr):
                return getattr(widget, attr)
        return widget

    def _register_drop_target(self, widget, callback, *dnd_types):
        target = self._get_native_widget(widget)
        target.drop_target_register(*dnd_types)
        target.dnd_bind("<<Drop>>", callback)

    def _on_file_drop(self, event):
        try:
            dropped_files = self.root.tk.splitlist(event.data)
            file_path = dropped_files[0] if dropped_files else event.data
        except Exception:
            file_path = event.data
        file_path = file_path.strip()

        if file_path.lower().endswith(('.xlsx', '.xls')):
            self.file_var.set(file_path)
            self.status_var.set("● FILE DROPPED")
            self.status_color_var.set("success")
            self._update_status_color()
            self.toast.show("File dropped successfully!", "success")
        else:
            self.toast.show("Please drop a valid Excel file (.xlsx, .xls)", "error")
        return COPY

    def _on_direct_drop(self, event):
        self._clear_direct_placeholder()
        text = event.data.strip()
        if not text:
            return COPY

        current = self.direct_input_textbox.get("1.0", "end").strip()
        if current:
            self.direct_input_textbox.insert("end", "\n")
        self.direct_input_textbox.insert("end", text)
        self.direct_input_textbox.configure(text_color=THEME["text_primary"])

        count = len(self._get_direct_values())
        self.status_var.set(f"● {count} VALUE{'S' if count != 1 else ''} ADDED")
        self.status_color_var.set("success")
        self._update_status_color()
        self._update_direct_count()
        self.toast.show(f"Added {count} values", "success")
        return COPY

    def _direct_placeholder_text(self):
        labels = {
            "ORDER": "orders", "CID": "CIDs",
            "SO": "SO numbers", "ORD": "ORD numbers",
        }
        label = labels.get(self.mode_var.get(), "values")
        return f"Paste or drag {label} here, one per line or separated by comma/space"

    def _refresh_direct_placeholder(self, old_placeholder):
        if not self.direct_input_textbox:
            return
        current = self.direct_input_textbox.get("1.0", "end").strip()
        if not current or current == old_placeholder:
            self.direct_input_textbox.delete("1.0", "end")
            self.direct_input_textbox.insert(
                "1.0", self._direct_placeholder_text()
            )
            self.direct_input_textbox.configure(
                text_color=THEME["text_secondary"]
            )

    def _clear_direct_placeholder(self, event=None):
        if not self.direct_input_textbox:
            return
        current = self.direct_input_textbox.get("1.0", "end").strip()
        if current == self._direct_placeholder_text():
            self.direct_input_textbox.delete("1.0", "end")
            self.direct_input_textbox.configure(
                text_color=THEME["text_primary"]
            )

    def _restore_direct_placeholder(self, event=None):
        if not self.direct_input_textbox:
            return
        current = self.direct_input_textbox.get("1.0", "end").strip()
        if not current:
            self.direct_input_textbox.insert(
                "1.0", self._direct_placeholder_text()
            )
            self.direct_input_textbox.configure(
                text_color=THEME["text_secondary"]
            )

    def clear_direct_input(self):
        if not self.direct_input_textbox:
            return
        self.direct_input_textbox.delete("1.0", "end")
        self._restore_direct_placeholder()
        self._update_direct_count()
        self.toast.show("Input cleared", "info")

    def _schedule_direct_count_update(self, event=None):
        if self._direct_count_timer is not None:
            try:
                self.root.after_cancel(self._direct_count_timer)
            except Exception:
                pass
        self._direct_count_timer = self.root.after(150, self._update_direct_count)

    def _update_direct_count(self):
        self._direct_count_timer = None
        if not self.direct_count_label:
            return
        count = len(self._get_direct_values())
        self.direct_count_label.configure(text=f"{count} added")
        self.stat_values_label.configure(text=str(count))

    def _get_direct_values(self):
        if not self.direct_input_textbox:
            return []

        text = self.direct_input_textbox.get("1.0", "end").strip()
        if not text or text == self._direct_placeholder_text():
            return []

        mode_headers = {"ORDER", "ORDERID", "ORDERS", "CID", "SO", "ORD"}
        values = []
        seen = set()

        for token in re.split(r"[\s,;]+", text):
            value = token.strip().strip("\"'")
            if not value or value.upper() in mode_headers:
                continue
            if value not in seen:
                values.append(value)
                seen.add(value)

        return values

    # =========================================================
    # Selection
    # =========================================================

    def select_all(self):
        for var in self.fields.values():
            var.set(True)
        self._update_count()
        self.toast.show("All fields selected", "success")

    def clear_all(self):
        for var in self.fields.values():
            var.set(False)
        self._update_count()
        self.file_var.set("")
        self.clear_direct_input()
        self.toast.show("All selections cleared", "info")

    # =========================================================
    # Smart Chat
    # =========================================================

    def open_smart_chat(self):
        if self.smart_chat_window is not None:
            try:
                if self.smart_chat_window.winfo_exists():
                    self.smart_chat_window.lift()
                    self.smart_chat_window.focus_force()
                    if self.smart_chat_entry:
                        self.smart_chat_entry.focus()
                    return
            except Exception:
                pass

        if not hasattr(self, 'chat_engine'):
            self.chat_engine = SmartChatEngine(self)

        window = ctk.CTkToplevel(self.root)
        self.smart_chat_window = window
        window.title("🤖 Smart Chat Pro")
        window.geometry("600x650")
        window.minsize(500, 500)
        window.configure(fg_color=THEME["bg"])
        window.transient(self.root)

        window.protocol("WM_DELETE_WINDOW", self._on_smart_chat_close)

        # Header
        header = ctk.CTkFrame(
            window, fg_color=THEME["surface"],
            corner_radius=CARD_RADIUS,
            border_width=1, border_color=THEME["border"]
        )
        header.pack(fill="x", padx=14, pady=(14, 0))

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(
            header_inner, text="🤖 Smart Chat Pro",
            text_color=THEME["accent"],
            font=title_font(20, "bold")
        ).pack(side="left")

        self.chat_status_indicator = ctk.CTkLabel(
            header_inner, text="● Connected",
            text_color=THEME["success"],
            font=ui_font(12)
        )
        self.chat_status_indicator.pack(side="right")

        # Chat Log
        log_frame = ctk.CTkFrame(
            window, fg_color=THEME["surface"],
            corner_radius=CARD_RADIUS,
            border_width=1, border_color=THEME["border"]
        )
        log_frame.pack(fill="both", expand=True, padx=14, pady=10)

        self.smart_chat_log = ctk.CTkTextbox(
            log_frame, height=350,
            corner_radius=CONTROL_RADIUS,
            border_width=0, fg_color=THEME["surface_2"],
            text_color=THEME["text_primary"],
            font=ui_font(13), wrap="word"
        )
        self.smart_chat_log.pack(fill="both", expand=True, padx=10, pady=10)
        self.smart_chat_log.configure(state="disabled")

        self.typing_indicator = ctk.CTkLabel(
            log_frame, text="",
            text_color=THEME["text_secondary"],
            font=ui_font(11), fg_color="transparent"
        )
        self.typing_indicator.pack(anchor="w", padx=10, pady=(0, 5))

        # Input Area
        input_card = ctk.CTkFrame(
            window, fg_color=THEME["surface"],
            corner_radius=CARD_RADIUS,
            border_width=1, border_color=THEME["border"]
        )
        input_card.pack(fill="x", padx=14, pady=(0, 14))

        input_inner = ctk.CTkFrame(input_card, fg_color="transparent")
        input_inner.pack(fill="x", padx=10, pady=10)
        input_inner.columnconfigure(0, weight=1)

        self.smart_chat_entry = ctk.CTkTextbox(
            input_inner, height=60,
            corner_radius=CONTROL_RADIUS,
            border_width=1, border_color=THEME["border"],
            fg_color=THEME["surface_2"],
            text_color=THEME["text_primary"],
            font=ui_font(13), wrap="word"
        )
        self.smart_chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.smart_chat_entry.bind(
            "<Control-Return>", lambda e: self._send_smart_chat()
        )
        self._attach_context_menu(self.smart_chat_entry)

        btn_col = ctk.CTkFrame(input_inner, fg_color="transparent")
        btn_col.grid(row=0, column=1, sticky="ns")

        self._primary_button(
            btn_col, "Send", self._send_smart_chat, width=85, height=32
        ).pack(pady=(0, 4))

        ctk.CTkButton(
            btn_col, text="🎤", command=self.start_listening,
            width=85, height=32, corner_radius=CONTROL_RADIUS,
            fg_color="#1e88e5", hover_color="#1565c0",
            text_color="white", cursor="hand2", font=ui_font(14)
        ).pack(pady=(4, 0))

        # Quick Actions
        quick_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        quick_frame.pack(fill="x", padx=10, pady=(0, 10))

        quick_actions = [
            ("Extract All", "full report"),
            ("Tech Check", "technical check"),
            ("Customer Profile", "customer profile"),
            ("Migration Audit", "migration audit")
        ]
        for label, preset in quick_actions:
            ctk.CTkButton(
                quick_frame, text=label,
                command=lambda p=preset: self._quick_chat_action(p),
                height=28, width=120,
                corner_radius=CONTROL_RADIUS,
                fg_color=THEME["surface_2"],
                text_color=THEME["text_primary"],
                border_width=1, border_color=THEME["border"],
                hover_color=THEME["accent_soft"],
                font=ui_font(11)
            ).pack(side="left", padx=(0, 6))

        # Welcome Message
        self._append_smart_chat(
            "Smart Assistant",
            "👋 Hello! I'm here to help you. Try typing something like:\n"
            "• 'Extract speed and CID for 12345, 67890'\n"
            "• 'Give me a full report for order 6051100'\n"
            "• Or click 🎤 and speak!"
        )
        self.smart_chat_entry.focus()

    def _on_smart_chat_close(self):
        """Cancel AI processing and close smart chat window safely."""
        self.ai_last_cancel_id += 1

        self.typing_indicator = None
        self.smart_chat_log = None
        self.smart_chat_entry = None

        if hasattr(self, 'chat_engine'):
            self.chat_engine.is_processing = False

        try:
            self.smart_chat_window.destroy()
        except Exception:
            pass
        self.smart_chat_window = None

    def _send_smart_chat(self):
        if not hasattr(self, 'smart_chat_entry') or not self.smart_chat_entry:
            return "break"

        if not self.smart_chat_window or not self.smart_chat_window.winfo_exists():
            return "break"

        text = self.smart_chat_entry.get("1.0", "end").strip()
        if not text:
            return "break"

        self.smart_chat_entry.delete("1.0", "end")
        self._append_smart_chat("You", text)

        if self.typing_indicator:
            self.typing_indicator.configure(text="Assistant is typing •••")

        def on_ai_response(data, from_cache=False):
            if not self.smart_chat_window or not self.smart_chat_window.winfo_exists():
                return
            if self.typing_indicator:
                self.typing_indicator.configure(text="")

            if from_cache:
                self._append_smart_chat(
                    "Smart Assistant",
                    "⚡ " + data.get("friendly_reply", "Settings applied.")
                )
            else:
                self._apply_ai_result(data)

        if hasattr(self, 'chat_engine'):
            success = self.chat_engine.process(text, on_ai_response)
            if not success:
                if self.typing_indicator:
                    self.typing_indicator.configure(text="")
                self._append_smart_chat(
                    "Smart Assistant", "⏳ Still processing the previous request..."
                )
        else:
            if self.typing_indicator:
                self.typing_indicator.configure(text="")
            self.apply_smart_request(text, from_chat=True)

        return "break"

    def _quick_chat_action(self, preset_name):
        presets = {
            "full report": "Extract full report for ",
            "technical check": "Technical check for IDs ",
            "customer profile": "Get customer info for ",
            "migration audit": "Migration audit for "
        }
        base_text = presets.get(preset_name, "Extract ")
        if self.smart_chat_entry:
            self.smart_chat_entry.delete("1.0", "end")
            self.smart_chat_entry.insert("1.0", base_text)
            self.smart_chat_entry.focus()

    def _append_smart_chat(self, sender, message):
        if not self.smart_chat_log:
            return
        if not self.smart_chat_window or not self.smart_chat_window.winfo_exists():
            return
        try:
            self.smart_chat_log.configure(state="normal")
            self.smart_chat_log.insert("end", f"👤 {sender}: {message}\n\n")
            self.smart_chat_log.see("end")
            self.smart_chat_log.configure(state="disabled")
        except Exception:
            pass

    # =========================================================
    # Voice Input
    # =========================================================

    def start_listening(self):
        if not self.smart_chat_window or not self.smart_chat_window.winfo_exists():
            return

        self._append_smart_chat("Smart Assistant", "🎤 Listening...")

        def listen_thread():
            try:
                import speech_recognition as sr
            except ImportError:
                self.root.after(0, lambda: self._append_smart_chat(
                    "Smart Assistant",
                    "❌ Speech recognition not installed. "
                    "Install with: pip install SpeechRecognition"
                ))
                return

            r = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.5)
                    audio = r.listen(source, timeout=5, phrase_time_limit=10)

                text = r.recognize_google(audio, language="en-US")
                self.root.after(0, lambda: self._process_voice_input(text))

            except sr.WaitTimeoutError:
                self.root.after(0, lambda: self._append_smart_chat(
                    "Smart Assistant", "⏱️ Timeout. Please try again."
                ))
            except sr.UnknownValueError:
                self.root.after(0, lambda: self._append_smart_chat(
                    "Smart Assistant", "🤷 Sorry, I didn't understand that."
                ))
            except Exception as e:
                err_msg = str(e)
                if "'NoneType' object has no attribute 'close'" not in err_msg:
                    self.root.after(0, lambda: self._append_smart_chat(
                        "Smart Assistant", f"❌ Mic Error: {err_msg}"
                    ))

        threading.Thread(target=listen_thread, daemon=True).start()

    def _process_voice_input(self, text):
        """Process voice recognized text through the chat engine."""
        self._append_smart_chat("You (Voice)", text)

        if self.smart_chat_entry:
            self.smart_chat_entry.delete("1.0", "end")
            self.smart_chat_entry.insert("1.0", text)

        if self.typing_indicator:
            self.typing_indicator.configure(text="Assistant is typing •••")

        def on_ai_response(data, from_cache=False):
            if not self.smart_chat_window or not self.smart_chat_window.winfo_exists():
                return
            if self.typing_indicator:
                self.typing_indicator.configure(text="")
            if from_cache:
                self._append_smart_chat(
                    "Smart Assistant",
                    "⚡ " + data.get("friendly_reply", "Settings applied.")
                )
            else:
                self._apply_ai_result(data)

        if hasattr(self, 'chat_engine'):
            self.chat_engine.process(text, on_ai_response)
        else:
            if self.typing_indicator:
                self.typing_indicator.configure(text="")
            self.apply_smart_request(text, from_chat=True)

    # =========================================================
    # TTS
    # =========================================================

    def speak_text(self, text, lang_hint=None):
        if not self.voice_enabled or not text:
            return

        if self.is_speaking:
            return

        if lang_hint is None:
            lang_hint = self.detect_chat_language(text)

        def speak_thread():
            import pygame
            temp_file = None
            self.is_speaking = True
            try:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass

                if lang_hint == "en":
                    try:
                        headers = {
                            "Authorization": f"Bearer {self.ai_api_key}"
                        }
                        payload = {
                            "model": "tts-1",
                            "input": text[:1000],
                            "voice": "alloy"
                        }
                        response = requests.post(
                            self.tts_api_url, headers=headers,
                            json=payload, timeout=15
                        )
                        if response.status_code == 200:
                            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
                            os.close(fd)
                            with open(temp_file, "wb") as f:
                                f.write(response.content)
                            pygame.mixer.music.load(temp_file)
                            pygame.mixer.music.play()
                            while pygame.mixer.music.get_busy():
                                pygame.time.Clock().tick(10)
                            return
                    except Exception:
                        pass

                try:
                    import edge_tts

                    fd, temp_file = tempfile.mkstemp(suffix=".mp3")
                    os.close(fd)

                    if lang_hint in ("ar_fusha", "ar_eg_colloquial"):
                        voice = "ar-EG-SalmaNeural"
                    else:
                        voice = "en-US-AvaNeural"

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        communicate = edge_tts.Communicate(text[:1000], voice)
                        loop.run_until_complete(communicate.save(temp_file))
                    finally:
                        loop.close()

                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)

                except Exception as e:
                    print(f"TTS Error: {e}")
            finally:
                self.is_speaking = False
                if temp_file:
                    try:
                        time.sleep(0.5)
                        os.remove(temp_file)
                    except Exception:
                        pass

        threading.Thread(target=speak_thread, daemon=True).start()

    # =========================================================
    # AI Result Application
    # =========================================================

    def _apply_ai_result(self, data):
        """Apply AI results to the UI with validation."""
        valid_modes = {"ORDER", "CID", "SO", "ORD"}
        if data.get("mode"):
            mode = str(data["mode"]).upper()
            if mode in valid_modes:
                self._set_mode(mode)

        if data.get("values") and len(data["values"]) > 0:
            self._set_direct_values(data["values"])

        if data.get("fields") and len(data["fields"]) > 0:
            target_fields = set()
            for f in data["fields"]:
                if f in self.fields:
                    target_fields.add(f)
                else:
                    for field_name in self.fields:
                        if field_name.lower() == f.lower():
                            target_fields.add(field_name)
                            break

            for name, var in self.fields.items():
                should_be_active = name in target_fields
                var.set(should_be_active)

            self._update_count()

        reply = data.get("friendly_reply", "Settings updated.")
        self._append_smart_chat("Smart Assistant", reply)

        self.speak_text(reply)

        if data.get("wants_to_save") and data.get("values") and data.get("fields"):
            self._append_smart_chat(
                "Smart Assistant",
                "Starting extraction and saving process now... 🚀"
            )
            self.start()

    def publish_smart_result(self, rows, out_excel, headers):
        def update():
            if not self.smart_chat_window or not self.smart_chat_window.winfo_exists():
                return
            message = self._format_smart_result(rows, out_excel, headers)
            self._append_smart_chat("Smart Assistant", message)

        self.root.after(0, update)

    def _format_smart_result(self, rows, out_excel, headers):
        rows = rows or []
        headers = headers or []

        if not rows:
            return (
                f"I finished the search, but unfortunately no matching "
                f"data was found.\nSaved file: {out_excel}"
            )

        max_rows = 10
        max_value_length = 180
        lines = [f"Extraction successful! Found {len(rows)} record(s).", ""]

        for index, row in enumerate(rows[:max_rows], start=1):
            lines.append(f"Result {index}:")
            for header in headers:
                value = row.get(header, "")
                if value is None or value == "":
                    continue
                value = str(value).strip()
                if len(value) > max_value_length:
                    value = value[:max_value_length - 3] + "..."
                lines.append(f"- {header}: {value}")
            lines.append("")

        remaining = len(rows) - max_rows
        if remaining > 0:
            lines.append(f"... and there are {remaining} more records in the file.")
            lines.append("")

        lines.append(f"📁 File saved at: {out_excel}")
        return "\n".join(lines).strip()

    # =========================================================
    # Smart Request Parsing
    # =========================================================

    def apply_smart_request(self, request_text=None, execute=False, from_chat=False):
        request_text = request_text or ""
        if not request_text:
            if from_chat:
                self._append_smart_chat(
                    "Smart Assistant", "Please tell me what you need first."
                )
            else:
                self.toast.show("Please enter what data you need first", "warning")
            return

        normalized_text = self._normalize_smart_text(request_text)
        wants_to_run = any(word in normalized_text for word in [
            "احفظ", "استخرج", "سجل", "ابدأ", "طلع", "عايز", "محتاج",
            "هات", "run", "save", "start", "extract", "go"
        ])

        result = self._parse_smart_request(normalized_text)

        if wants_to_run and self.is_running:
            if from_chat:
                self._append_smart_chat(
                    "Smart Assistant",
                    "There is an extraction process currently running. "
                    "Please wait or stop it first."
                )
            else:
                self.toast.show("Extraction already in progress", "warning")
            return

        if result["file_path"]:
            self.file_var.set(result["file_path"])

        if result["mode"]:
            self._set_mode(result["mode"])

        if result["values"]:
            self._set_direct_values(result["values"])

        if result["fields"]:
            for var in self.fields.values():
                var.set(False)
            for field in result["fields"]:
                if field in self.fields:
                    self.fields[field].set(True)
            self._update_count()

        parts = []
        if result["mode"]:
            parts.append(f"mode: {result['mode']}")
        if result["values"]:
            parts.append(f"{len(result['values'])} value(s)")
        if result["fields"]:
            parts.append(f"{len(result['fields'])} field(s)")

        if self.smart_hint_label:
            if parts:
                self.smart_hint_label.configure(
                    text="Detected " + ", ".join(parts)
                )
            else:
                self.smart_hint_label.configure(
                    text="No fields or identifiers were detected. "
                         "Try using field names like CID, customer name, status, speed."
                )

        self.status_var.set("SMART REQUEST APPLIED")
        self.status_color_var.set("success")
        self._update_status_color()

        if from_chat:
            if parts:
                msg = "Understood. I have prepared " + " and ".join(parts) + ".\n"
                if wants_to_run:
                    msg += "I'm starting the extraction and saving process now..."
                else:
                    msg += ("Should I start the extraction and save to Excel now? "
                            "(Type 'start' or 'save')")
                self._append_smart_chat("Smart Assistant", msg)
                self.speak_text(msg)
            elif any(greet in normalized_text for greet in
                     ["هلا", "مرحبا", "سلام", "اهلا", "صباح", "مساء"]):
                msg = ("Hello! I'm Smart Assistant, ready to help you "
                       "extract ECRM data. What do we need to do today?")
                self._append_smart_chat("Smart Assistant", msg)
                self.speak_text(msg)
            else:
                msg = ("Hello. You can tell me the customer data or numbers "
                       "you want to extract (e.g., 'Extract speed for 12345') "
                       "and I'll get to work.")
                self._append_smart_chat("Smart Assistant", msg)
                self.speak_text(msg)

        if wants_to_run:
            has_input = bool(self.file_var.get() or self._get_direct_values())
            has_fields = any(v.get() for v in self.fields.values())

            if has_input and has_fields:
                self.start()
            else:
                if from_chat:
                    self._append_smart_chat(
                        "Smart Assistant",
                        "I cannot start without identifying the order numbers "
                        "and required fields first."
                    )
                else:
                    self.toast.show("Please provide input and select fields first", "warning")

    def _parse_smart_request(self, text):
        normalized = self._normalize_smart_text(text)
        mode = self._detect_smart_mode(normalized)
        fields = self._detect_smart_fields(text, normalized)
        values = self._detect_smart_values(text)
        file_path = self._detect_smart_file_path(text)

        return {
            "mode": mode, "fields": fields,
            "values": values, "file_path": file_path
        }

    def _normalize_smart_text(self, text):
        text = text.lower()
        replacements = {
            "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        return re.sub(r"\s+", " ", text).strip()

    def _detect_smart_mode(self, normalized):
        if re.search(r"\b(service order|so numbers?|so id|so:|so)\b", normalized):
            return "SO"
        if re.search(r"\b(ord numbers?|ord id|ord:|ord)\b", normalized):
            return "ORD"
        if re.search(r"\b(order|orders|order id|orderid)\b", normalized) or "اوردر" in normalized or "الطلب" in normalized:
            return "ORDER"
        if re.search(r"\b(cids?|circuit ids?|cid:)\b", normalized) or "سيركت" in normalized or "دائره" in normalized:
            return "CID"
        return None

    def _detect_smart_file_path(self, text):
        match = re.search(r"[A-Za-z]:\\[^,\n;]+?\.xlsx?", text, re.IGNORECASE)
        return match.group(0).strip("\"' ") if match else ""

    def _detect_smart_values(self, text):
        file_path = self._detect_smart_file_path(text)
        clean_text = text.replace(file_path, " ") if file_path else text
        tokens = re.findall(
            r"\b(?:[A-Za-z]*\d[A-Za-z0-9_-]{3,}|6\d{6}|5\d{6})\b",
            clean_text
        )
        values = []
        seen = set()
        for token in tokens:
            value = token.strip().strip("\"'")
            if value.lower().endswith((".xlsx", ".xls")):
                continue
            if value not in seen:
                values.append(value)
                seen.add(value)
        return values

    def _detect_smart_fields(self, original, normalized):
        if (re.search(r"\b(full report|all fields|everything|all data)\b", normalized)
                or "كل الداتا" in normalized or "تقرير كامل" in normalized):
            return list(FIELD_OPTIONS)

        aliases = self._smart_field_aliases()
        detected = []
        compact = re.sub(r"[^a-z0-9ا-ي]+", "", normalized)

        for field in FIELD_OPTIONS:
            field_terms = aliases.get(field, [])
            field_terms.append(field)
            for term in field_terms:
                term_norm = self._normalize_smart_text(term)
                term_compact = re.sub(r"[^a-z0-9ا-ي]+", "", term_norm)
                if term_norm and self._smart_term_matches(term_norm, normalized):
                    detected.append(field)
                    break
                if term_compact and len(term_compact) > 3 and term_compact in compact:
                    detected.append(field)
                    break

        return list(dict.fromkeys(detected))

    def _smart_term_matches(self, term, normalized):
        if re.fullmatch(r"[a-z0-9]+", term):
            return re.search(rf"\b{re.escape(term)}\b", normalized) is not None
        return term in normalized

    def _smart_field_aliases(self):
        return {
            "Order": ["order id", "order number", "orders", "رقم الطلب", "اوردر"],
            "CST Name": ["customer", "customer name", "client name", "اسم العميل", "اسم الزبون", "cst name"],
            "CST Name Arabic": ["arabic customer", "customer arabic", "اسم العميل عربي", "cst name arabic"],
            "CST Number": ["customer number", "account number", "رقم العميل", "cst number"],
            "CST Type": ["customer type", "نوع العميل", "cst type"],
            "CST Category": ["customer category", "تصنيف العميل", "cst category"],
            "Branch": ["branch", "فرع"],
            "Branch Address": ["branch address", "عنوان الفرع"],
            "Account manager": ["account manager", "am name", "مدير الحساب"],
            "Account manager mail": ["account manager mail", "account manager email", "am email", "mail", "email", "ايميل"],
            "Order Status": ["order status", "status", "حاله الطلب", "حالة الطلب"],
            "SO Type": ["so type", "service order type"],
            "SO Status": ["so status", "service order status"],
            "Latest SO": ["latest so", "last so", "اخر so"],
            "Current Task": ["current task", "task", "المهمه الحاليه", "التاسك"],
            "Latest Migration by E-Support SO": ["migration", "migration so", "latest migration", "مايجريشن"],
            "Migration SO Type": ["migration type"],
            "Migration SO Status": ["migration status"],
            "Migration Current Task": ["migration task"],
            "Migration Current Task Owner": ["migration owner", "task owner"],
            "CID": ["cid", "circuit id", "circuit", "سيركت", "دائره"],
            "Request Number": ["request number", "ord", "old ord", "new ord", "رقم الريكوست"],
            "ESPT & infra status": ["espt", "infra", "infra status", "infrastructure", "حاله الانفرا"],
            "Notes": ["notes", "note", "comment", "ملاحظات"],
            "NID": ["nid"],
            "Speed": ["speed", "bandwidth", "سرعه", "السرعه"],
            "Hardware": ["hardware", "device", "router"],
            "Product": ["product", "service product", "منتج"],
            "Transmission Type": ["transmission", "transmission type"],
            "Network Data": ["network data", "network", "l3", "vlan", "pe ip", "wan ip", "vrf", "lan"],
            "MSAN Data": ["msan", "msan data", "msan ip", "shelf", "card", "port"],
            "POP": ["pop"],
            "Work Order PDF": ["work order", "wo pdf", "pdf"],
            "Installed Resources": ["installed resources", "installed base", "resources"],
        }

    def _set_direct_values(self, values):
        if not self.direct_input_textbox:
            return
        string_values = [str(v) for v in values]
        self.direct_input_textbox.delete("1.0", "end")
        self.direct_input_textbox.insert("1.0", "\n".join(string_values))
        self.direct_input_textbox.configure(text_color=THEME["text_primary"])
        self._update_direct_count()

    # =========================================================
    # Theme toggle with field style refresh
    # =========================================================

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        ctk.set_appearance_mode("Dark" if self.is_dark else "Light")
        self.theme_btn.configure(text="🌙 Theme" if self.is_dark else "☀ Theme")
        self._update_status_color()

        self.root.after(100, self._refresh_field_styles)

    def ask_yes_no(self, title, message):
        return messagebox.askyesno(title, message, parent=self.root)

    def is_cancelled(self):
        return self.cancel_requested

    def cancel(self):
        if not self.is_running:
            return

        self.cancel_requested = True
        self.start_btn.configure(
            text="Cancelling...",
            fg_color=THEME["error"],
            hover_color=THEME["error"],
            state="disabled"
        )
        self.status_var.set("● CANCEL REQUESTED")
        self.status_color_var.set("warning")
        self._update_status_color()
        self.toast.show("Cancellation requested", "warning")

    # =========================================================
    # Reset
    # =========================================================

    def reset_ui(self, reset_progress=True):
        self.is_running = False
        self.cancel_requested = False

        self._stop_processing_animation()

        self.start_btn.configure(
            text="🚀 Start Extraction\nExtract data to Excel",
            fg_color=THEME["accent"],
            hover_color=THEME["accent_hover"],
            state="normal"
        )

        self.status_color_var.set("success")
        self.status_var.set("● READY")
        self._update_status_color()

        if reset_progress:
            self.progress.set(0)
            if hasattr(self, "stat_progress_label") and self.stat_progress_label:
                self.stat_progress_label.configure(text="0%")

    # =========================================================
    # Start
    # =========================================================

    def start(self):
        if self.is_running:
            self.cancel()
            return

        direct_values = self._get_direct_values()

        if not self.file_var.get() and not direct_values:
            self.toast.show("Please select Excel file or paste orders", "error")
            self.status_var.set("● NO INPUT SELECTED")
            self.status_color_var.set("warning")
            self._update_status_color()
            return

        selected = [n for n, v in self.fields.items() if v.get()]

        if not selected:
            self.toast.show("Please select at least one field", "warning")
            self.status_var.set("● NO FIELDS SELECTED")
            self.status_color_var.set("warning")
            self._update_status_color()
            return

        # NEW: بدء جلسة analytics
        self.analytics.start_session()
        self.extraction_count += 1

        self.is_running = True
        self.cancel_requested = False

        self.start_btn.configure(
            text="🚫 Cancel Extraction",
            fg_color=THEME["error"],
            hover_color=THEME["error"],
            state="normal"
        )

        self._start_processing_animation()

        self.status_var.set("● PROCESSING")
        self.status_color_var.set("warning")
        self._update_status_color()
        self.toast.show("Extraction started...", "info")

        extraction_thread = threading.Thread(
            target=self._run_extraction, args=(self.context,), daemon=True
        )
        extraction_thread.start()
        
    def _run_extraction(self, context):
        """Wrapper لتشغيل الاستخراج وتسجيل النتائج"""
        try:
            self.on_start(context)
            # تسجيل النجاح
            self.analytics.record_extraction(
                context.mode, 
                len(context.selected_fields),
                len(context.direct_values),
                success=True
            )
            self.root.after(0, lambda: self.toast.show("Extraction completed successfully!", "success"))
        except Exception as e:
            # تسجيل الفشل
            self.analytics.record_extraction(
                context.mode,
                len(context.selected_fields),
                len(context.direct_values),
                success=False
            )
            self.root.after(0, lambda: self.toast.show(f"Extraction failed: {e}", "error"))
            raise