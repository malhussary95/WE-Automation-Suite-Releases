import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

URL = "http://172.29.29.108:8888/"
DRIVER_PATH = r"D:\WebDriver\bin\chromedriver.exe"

CREDENTIALS_FILE = BASE_DIR / "credentials.json"

DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""

def _load_credentials():
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            u = data.get("username", DEFAULT_USERNAME)
            p = data.get("password", DEFAULT_PASSWORD)
            if u:
                return u, p
        except Exception:
            pass
    return DEFAULT_USERNAME, DEFAULT_PASSWORD

def save_credentials(username: str, password: str):
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump({"username": username, "password": password}, f, indent=2, ensure_ascii=False)

USERNAME, PASSWORD = _load_credentials()

EXCEL_INPUT = str(BASE_DIR / "DB.xlsx")
EXCEL_OUTPUT = str(BASE_DIR / "DB_updated.xlsx")

SHEET_MAPPING = {
    "wimax": "WiMax Template",
    "ftth": "FTTH Template",
}

