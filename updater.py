from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


# ============================================================
# WE Automation Suite - Auto Updater
# ============================================================

OWNER = "malhussary95"
REPO = "WE-Automation-Suite-Releases"

GITHUB_LATEST_API = (
    f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
)

APP_DIR = Path(__file__).resolve().parent
VERSION_FILE = APP_DIR / "version.json"


# ============================================================
# User data / runtime files
# These files MUST survive application updates.
# ============================================================

PROTECTED_FILES = {
    "credentials.json",
    "ecrm_autosave.json",

    "ECRM/credentials.json",
    "ECRM/ecrm_autosave.json",

    "DB/DB.xlsx",

    "ECRM/Input/Data.xlsx",
    "FTTH portal/input.xlsx",
    "PSC extractor/input.xlsx",
}


PROTECTED_DIRS = {
    "RR_DEBUG",
    "webapp/uploads",
    "WO Unified/input",
}


# ============================================================
# Updater itself
#
# IMPORTANT:
# The running updater must NOT overwrite itself.
# ============================================================

SELF_FILE = "updater.py"


# ============================================================
# Version handling
# ============================================================

def normalize_version(value: str) -> tuple[int, ...]:
    """
    Convert versions such as:
        13.0.0
        v13.0.0
        13.1
    into comparable tuples.
    """

    value = str(value).strip().lower()

    if value.startswith("v"):
        value = value[1:]

    parts = []

    for part in value.split("."):
        digits = ""

        for char in part:
            if char.isdigit():
                digits += char
            else:
                break

        parts.append(int(digits or "0"))

    while len(parts) < 3:
        parts.append(0)

    return tuple(parts)


def read_local_version() -> str:

    if not VERSION_FILE.exists():
        return "0.0.0"

    try:
        with VERSION_FILE.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)

        return str(data.get("version", "0.0.0"))

    except Exception:
        return "0.0.0"


# ============================================================
# GitHub
# ============================================================

def get_latest_release() -> dict | None:

    request = urllib.request.Request(
        GITHUB_LATEST_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "WE-Automation-Suite-Updater",
            "Cache-Control": "no-cache",
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except Exception as e:

        print(
            f"[UPDATE] Could not check GitHub: {e}"
        )

        return None


# ============================================================
# Protected files
# ============================================================

def is_protected(relative_path: str) -> bool:

    relative_path = (
        relative_path
        .replace("\\", "/")
        .strip("/")
    )

    # --------------------------------------------------------
    # updater.py must never be overwritten by itself
    # --------------------------------------------------------

    if relative_path.lower() == SELF_FILE.lower():
        return True

    # --------------------------------------------------------
    # Exact protected user files
    # --------------------------------------------------------

    if relative_path in PROTECTED_FILES:
        return True

    # --------------------------------------------------------
    # Protected directories
    # --------------------------------------------------------

    for protected_dir in PROTECTED_DIRS:

        protected_dir = (
            protected_dir
            .replace("\\", "/")
            .strip("/")
        )

        if (
            relative_path == protected_dir
            or relative_path.startswith(
                protected_dir + "/"
            )
        ):

            return True

    # --------------------------------------------------------
    # Python cache
    # --------------------------------------------------------

    if relative_path.endswith(".pyc"):
        return True

    if "__pycache__/" in relative_path:
        return True

    return False


# ============================================================
# Download
# ============================================================

def download_file(
    url: str,
    destination: Path,
) -> None:

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "WE-Automation-Suite-Updater",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=120,
    ) as response:

        with destination.open(
            "wb"
        ) as f:

            shutil.copyfileobj(
                response,
                f,
            )


# ============================================================
# Install update
# ============================================================

def copy_update_files(
    extracted_dir: Path,
) -> None:

    """
    Copy application files from downloaded release.

    User files are preserved.

    updater.py is intentionally skipped because the updater
    itself is currently running.
    """

    for source in extracted_dir.rglob("*"):

        if source.is_dir():
            continue

        relative = source.relative_to(
            extracted_dir
        )

        relative_str = relative.as_posix()

        if is_protected(relative_str):

            if relative_str.lower() == SELF_FILE.lower():

                print(
                    f"[KEEP] {relative_str} "
                    "(running updater)"
                )

            else:

                print(
                    f"[KEEP] {relative_str}"
                )

            continue

        destination = APP_DIR / relative

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:

            shutil.copy2(
                source,
                destination,
            )

            print(
                f"[UPDATE] {relative_str}"
            )

        except Exception as e:

            print(
                f"[WARN] Could not update "
                f"{relative_str}: {e}"
            )


# ============================================================
# Temporary files
# ============================================================

def cleanup_temp(
    path: Path | None,
) -> None:

    if path and path.exists():

        try:

            shutil.rmtree(
                path,
                ignore_errors=True,
            )

        except Exception:
            pass


# ============================================================
# Perform update
# ============================================================

def perform_update(
    latest_version: str,
    download_url: str,
) -> bool:

    temp_root = None

    try:

        temp_root = Path(
            tempfile.mkdtemp(
                prefix="we_automation_update_"
            )
        )

        zip_path = (
            temp_root / "update.zip"
        )

        extract_dir = (
            temp_root / "extracted"
        )

        print()
        print("=" * 60)
        print(
            f"Downloading WE Automation Suite "
            f"{latest_version}"
        )
        print("=" * 60)

        download_file(
            download_url,
            zip_path,
        )

        print(
            "[OK] Download completed."
        )

        extract_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            "[..] Extracting update..."
        )

        with zipfile.ZipFile(
            zip_path,
            "r",
        ) as z:

            z.extractall(
                extract_dir
            )

        # ----------------------------------------------------
        # Handle ZIP with one top-level folder
        # ----------------------------------------------------

        entries = list(
            extract_dir.iterdir()
        )

        if (
            len(entries) == 1
            and entries[0].is_dir()
        ):

            source_dir = entries[0]

        else:

            source_dir = extract_dir

        print(
            "[..] Installing application files..."
        )

        copy_update_files(
            source_dir
        )

        print(
            "[OK] Update installed successfully."
        )

        return True

    except Exception as e:

        print()
        print(
            f"[ERROR] Update failed: {e}"
        )

        return False

    finally:

        cleanup_temp(
            temp_root
        )


# ============================================================
# Update check
# ============================================================

def check_for_updates() -> bool:

    local_version = (
        read_local_version()
    )

    print()
    print(
        "WE Automation Suite Auto Updater"
    )
    print(
        "-" * 40
    )

    print(
        f"Current version : "
        f"{local_version}"
    )

    release = (
        get_latest_release()
    )

    if not release:

        print(
            "[INFO] Update check skipped."
        )

        return False

    tag_name = str(
        release.get(
            "tag_name",
            "",
        )
    ).strip()

    latest_version = (
        tag_name.lstrip("vV")
    )

    print(
        f"Latest version  : "
        f"{latest_version}"
    )

    if not latest_version:

        print(
            "[INFO] GitHub release has "
            "no valid version."
        )

        return False

    if (
        normalize_version(
            latest_version
        )
        <=
        normalize_version(
            local_version
        )
    ):

        print(
            "[OK] Application is already "
            "up to date."
        )

        return False

    assets = release.get(
        "assets",
        []
    )

    if not assets:

        print(
            "[ERROR] GitHub release has "
            "no update asset."
        )

        return False

    # --------------------------------------------------------
    # Find ZIP asset
    # --------------------------------------------------------

    asset = None

    for item in assets:

        name = str(
            item.get(
                "name",
                "",
            )
        )

        if name.lower().endswith(
            ".zip"
        ):

            asset = item
            break

    if not asset:

        print(
            "[ERROR] No ZIP update asset found."
        )

        return False

    download_url = asset.get(
        "browser_download_url"
    )

    if not download_url:

        print(
            "[ERROR] Update download URL "
            "is missing."
        )

        return False

    print()
    print(
        f"[UPDATE] New version available: "
        f"{latest_version}"
    )

    print(
        f"[UPDATE] Asset: "
        f"{asset.get('name')}"
    )

    success = perform_update(
        latest_version,
        download_url,
    )

    if success:

        print()
        print(
            f"[OK] WE Automation Suite "
            f"updated to {latest_version}."
        )

        return True

    return False


# ============================================================
# Main
# ============================================================

def main() -> int:

    try:

        check_for_updates()

        return 0

    except KeyboardInterrupt:

        print()
        print(
            "[INFO] Update cancelled."
        )

        return 1

    except Exception as e:

        print(
            f"[ERROR] Updater error: {e}"
        )

        return 1


if __name__ == "__main__":

    sys.exit(
        main()
    )