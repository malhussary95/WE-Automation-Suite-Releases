import os

ECRM_BASE_URL = "https://ted-ecrm.te.eg/ECRM/"
BASE_URL = f"{ECRM_BASE_URL}api/data/v8.2"

# credentials.json is always beside main.py (project root).
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.json")
