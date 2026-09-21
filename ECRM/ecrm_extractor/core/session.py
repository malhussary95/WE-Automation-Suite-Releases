import json
import os

import requests
import urllib3
from requests_ntlm import HttpNtlmAuth

from ecrm_extractor.config import CREDENTIALS_FILE

urllib3.disable_warnings()

def create_session(username, password):
    session = requests.Session()
    session.auth = HttpNtlmAuth(
        username.strip(),
        password.strip()
    )
    session.verify = False
    session.headers.update({
        "Accept": "application/json",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Prefer": 'odata.include-annotations="*"'
    })
    return session


def save_credentials(username, password):
    data = {
        "username": username,
        "password": password
    }
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


def load_credentials():
    """Load username/password from the project-root credentials.json."""
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        username = str(data.get("username", "") or "").strip()
        password = str(data.get("password", "") or "").strip()
        return username, password
    except (OSError, json.JSONDecodeError, TypeError):
        return "", ""
