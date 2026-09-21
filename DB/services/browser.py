
from pathlib import Path
import os
import json
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ============================================================
# Configuration
# ============================================================

# Local ChromeDriver Path
CHROMEDRIVER = Path(r"D:\WebDriver\bin\chromedriver.exe")

# Website URL
URL = "http://172.29.29.108:8888"

# ============================================================
# Create Chrome Driver
# ============================================================

def create_driver(headless=False):
    """
    Create Chrome Driver using local ChromeDriver only.

    No webdriver-manager.
    No automatic driver download.
    No internet required.
    """

    # --------------------------------------------------------
    # Check ChromeDriver
    # --------------------------------------------------------

    if not CHROMEDRIVER.is_file():
        raise FileNotFoundError(
            "\n"
            "==================================================\n"
            "❌ ChromeDriver NOT FOUND\n"
            "==================================================\n"
            f"Expected path:\n{CHROMEDRIVER}\n"
            "\n"
            "Please make sure chromedriver.exe exists at this path.\n"
            "==================================================\n"
        )

    print(f"✅ ChromeDriver found: {CHROMEDRIVER}")

    # --------------------------------------------------------
    # Chrome Options
    # --------------------------------------------------------

    options = webdriver.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")

    # Optional stability options
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")

    # --------------------------------------------------------
    # ChromeDriver Service
    # --------------------------------------------------------

    service = Service(
        executable_path=str(CHROMEDRIVER)
    )

    # --------------------------------------------------------
    # Start Chrome
    # --------------------------------------------------------

    try:
        driver = webdriver.Chrome(
            service=service,
            options=options
        )

        print("✅ Chrome Driver started successfully")

        return driver

    except Exception as e:
        print("\n")
        print("==================================================")
        print("❌ Failed to start ChromeDriver")
        print("==================================================")
        print(f"ChromeDriver: {CHROMEDRIVER}")
        print(f"Error: {e}")
        print("==================================================")
        print("\n")

        raise


# ============================================================
# Login
# ============================================================

def login(driver, username, password, logger=print):
    """
    Login to the application.

    Parameters
    ----------
    driver : selenium webdriver
        Active Chrome driver.

    username : str
        Username.

    password : str
        Password.

    logger : function
        Logging function. Defaults to print.
    """

    # --------------------------------------------------------
    # Open Website
    # --------------------------------------------------------

    base_url = URL.rstrip("/")

    logger(f"🌐 Opening: {base_url}")

    driver.get(base_url)

    # --------------------------------------------------------
    # WebDriver Wait
    # --------------------------------------------------------

    wait = WebDriverWait(driver, 60)

    # ========================================================
    # Wait Login Page
    # ========================================================

    logger("⏳ Waiting for Login Page...")

    wait.until(
        EC.presence_of_element_located(
            (By.ID, "UserName")
        )
    )

    logger("🔑 Login Page Loaded")

    # ========================================================
    # Username
    # ========================================================

    logger("👤 Entering Username...")

    user_field = wait.until(
        EC.element_to_be_clickable(
            (By.ID, "UserName")
        )
    )

    driver.execute_script(
        """
        arguments[0].scrollIntoView(true);
        arguments[0].focus();
        arguments[0].click();
        """,
        user_field
    )

    time.sleep(1)

    user_field.clear()
    user_field.send_keys(username)

    # ========================================================
    # Password
    # ========================================================

    logger("🔐 Entering Password...")

    pass_field = wait.until(
        EC.element_to_be_clickable(
            (By.ID, "Password")
        )
    )

    driver.execute_script(
        """
        arguments[0].focus();
        arguments[0].click();
        """,
        pass_field
    )

    time.sleep(1)

    pass_field.clear()
    pass_field.send_keys(password)

    # ========================================================
    # Submit Login
    # ========================================================

    logger("🚀 Submitting Login...")

    submit_btn = wait.until(
        EC.element_to_be_clickable(
            (
                By.CSS_SELECTOR,
                "button[type='submit']"
            )
        )
    )

    submit_btn.click()

    # ========================================================
    # Wait for Redirect
    # ========================================================

    logger("⏳ Waiting for redirect to Home...")

    wait.until(
        lambda d: "/Home" in d.current_url
    )

    logger(
        f"✅ Redirected To: {driver.current_url}"
    )

    # ========================================================
    # Wait Full Page Load
    # ========================================================

    logger("⏳ Waiting page fully loaded...")

    wait.until(
        lambda d: d.execute_script(
            "return document.readyState"
        ) == "complete"
    )

    # ========================================================
    # Wait Dashboard
    # ========================================================

    logger("⏳ Waiting for Dashboard...")

    wait.until(
        EC.presence_of_element_located(
            (By.ID, "accordionSidebar")
        )
    )

    wait.until(
        EC.presence_of_element_located(
            (By.ID, "wrapper")
        )
    )

    logger("✅ Dashboard Loaded Successfully")

    # --------------------------------------------------------
    # Extra wait because the application is heavy
    # --------------------------------------------------------

    time.sleep(3)

    logger("✅ Login Successful")

    return True


# ============================================================
# Example Usage
# ============================================================

if __name__ == "__main__":

    creds_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "credentials.json")
    if os.path.exists(creds_file):
        with open(creds_file, "r", encoding="utf-8") as f:
            creds = json.load(f)
        USERNAME = creds.get("username", "")
        PASSWORD = creds.get("password", "PUT_YOUR_PASSWORD_HERE")
    else:
        USERNAME = ""
        PASSWORD = "PUT_YOUR_PASSWORD_HERE"

    driver = None

    try:

        # ----------------------------------------------------
        # Start Chrome
        # ----------------------------------------------------

        driver = create_driver(
            headless=False
        )

        # ----------------------------------------------------
        # Login
        # ----------------------------------------------------

        login(
            driver,
            USERNAME,
            PASSWORD
        )

        # Keep browser open
        input(
            "\nPress ENTER to close browser..."
        )

    except Exception as e:

        print("\n")
        print("==================================================")
        print("❌ ERROR")
        print("==================================================")
        print(e)
        print("==================================================")

    finally:

        if driver:
            driver.quit()
            print("🔴 Browser closed")

