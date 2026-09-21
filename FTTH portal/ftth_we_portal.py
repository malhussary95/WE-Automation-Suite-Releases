import os
import time
import re
import threading
import base64
import io
import json
import pandas as pd
import customtkinter as ctk
from PIL import Image


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


URL = 'https://ftth.te.eg/ftthPortal/#/login'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.json')
DEFAULT_INPUT_FILE = os.path.join(SCRIPT_DIR, 'input.xlsx')
DEFAULT_OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'output.xlsx')

# ─── WE Brand Colors ───
WE_PURPLE = '#6B2D8E'
WE_PURPLE_LIGHT = '#8E44AD'
WE_PURPLE_DARK = '#4A1F63'
BG_COLOR = '#F3F0F7'
CARD_BG = '#FFFFFF'
TEXT_COLOR = '#2D2D2D'
PLACEHOLDER = '#999999'
ERROR_COLOR = '#E74C3C'


def create_chrome_driver(headless=True):
    options = webdriver.ChromeOptions() 
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    # Use webdriver-manager to automatically handle the chromedriver
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def show_login_captcha_popup(
    image_bytes: bytes,
    username_prefill: str = "",
    password_prefill: str = "",
    attempt: int = 1,
    max_attempts: int = 5,
    parent=None
    ) -> dict:

    result = {
        "username": "",
        "password": "",
        "captcha": None
    }

    if parent:
        root = ctk.CTkToplevel(parent)
        root.transient(parent) # تجعل النافذة تابعة للرئيسية
    else:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()

    root.title("WE FTTH Portal")
  
    root.resizable(False, False)
    root.attributes("-topmost", True)

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()

    x = int((screen_w / 2) - (620 / 2))
    y = int((screen_h / 2) - (760 / 2))

    root.geometry(f"650x850+{x}+{y}")

    main = ctk.CTkFrame(
        root,
        fg_color="#FFFFFF",
        corner_radius=20
    )
    main.pack(fill="both", expand=True, padx=20, pady=20)

    logo_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data",
        "We_logo.png"
    )

    try:
        logo = ctk.CTkImage(
            light_image=Image.open(logo_path),
            size=(180, 80)
        )
        ctk.CTkLabel(
            main,
            image=logo,
            text=""
        ).pack(pady=(20, 5))

    except Exception:
        ctk.CTkLabel(
            main,
            text="WE",
            font=("Segoe UI", 42, "bold"),
            text_color="#6B2D8E"
        ).pack(pady=(20, 5))

    ctk.CTkLabel(
        main,
        text="FTTH Assurance Portal",
        font=("Segoe UI", 22, "bold"),
        text_color="#6B2D8E"
    ).pack()

    ctk.CTkLabel(
        main,
        text="Telecom Egypt",
        font=("Segoe UI", 12),
        text_color="gray"
    ).pack(pady=(0, 15))

    progress = ctk.CTkProgressBar(
        main,
        width=450,
        progress_color="#6B2D8E"
    )
    progress.pack(pady=(0, 10))
    progress.set(attempt / max_attempts)

    ctk.CTkLabel(
        main,
        text=f"CAPTCHA Attempt {attempt}/{max_attempts}",
        font=("Segoe UI", 11)
    ).pack()

    ctk.CTkLabel(
        main,
        text="Username",
        anchor="w",
        font=("Segoe UI", 13, "bold")
    ).pack(fill="x", padx=60, pady=(25, 5))

    entry_user = ctk.CTkEntry(
        main,
        height=42,
        corner_radius=10,
        font=("Segoe UI", 13)
    )
    entry_user.pack(fill="x", padx=60)
    entry_user.insert(0, username_prefill)

    ctk.CTkLabel(
        main,
        text="Password",
        anchor="w",
        font=("Segoe UI", 13, "bold")
    ).pack(fill="x", padx=60, pady=(15, 5))

    pass_frame = ctk.CTkFrame(
        main,
        fg_color="transparent"
    )
    pass_frame.pack(fill="x", padx=60)

    entry_pass = ctk.CTkEntry(
        pass_frame,
        height=42,
        show="●",
        font=("Segoe UI", 13)
    )
    entry_pass.pack(side="left", fill="x", expand=True)
    entry_pass.insert(0, password_prefill)

    def toggle_password():
        if entry_pass.cget("show") == "":
            entry_pass.configure(show="●")
            btn_show.configure(text="👁")
        else:
            entry_pass.configure(show="")
            btn_show.configure(text="🙈")

    btn_show = ctk.CTkButton(
        pass_frame,
        text="👁",
        width=45,
        command=toggle_password,
        fg_color="#6B2D8E",
        hover_color="#4A1F63"
    )
    btn_show.pack(side="left", padx=(8, 0))

    ctk.CTkLabel(
        main,
        text="CAPTCHA",
        anchor="w",
        font=("Segoe UI", 13, "bold")
    ).pack(fill="x", padx=60, pady=(20, 8))

    captcha_img = Image.open(io.BytesIO(image_bytes))

    # استخدام try لضمان عدم توقف البرنامج بسبب الصور في حالة تعدد الـ Roots
    try:
        captcha = ctk.CTkImage(
            light_image=captcha_img,
            size=(280, 80)
        )
    except Exception:
        captcha = None

    captcha_frame = ctk.CTkFrame(
        main,
        corner_radius=12,
        border_width=2,
        border_color="#6B2D8E"
    )
    captcha_frame.pack(padx=60, pady=5)

    if captcha:
        ctk.CTkLabel(
            captcha_frame,
            image=captcha,
            text=""
        ).pack(padx=10, pady=10)
    else:
        ctk.CTkLabel(captcha_frame, text="[CAPTCHA IMAGE]").pack(padx=10, pady=10)

    ctk.CTkLabel(
        main,
        text="Enter CAPTCHA Code",
        font=("Segoe UI", 11),
        text_color="gray"
    ).pack(pady=(10, 5))

    entry_captcha = ctk.CTkEntry(
        main,
        height=50,
        corner_radius=12,
        justify="center",
        font=("Consolas", 18, "bold")
    )
    entry_captcha.pack(fill="x", padx=60)

    lbl_error = ctk.CTkLabel(
        main,
        text="",
        text_color="red",
        font=("Segoe UI", 11, "bold")
    )
    lbl_error.pack(pady=(5, 10))

    def submit(event=None):
        u = entry_user.get().strip()
        p = entry_pass.get().strip()
        c = entry_captcha.get().strip()

        if not u:
            lbl_error.configure(text="Username required")
            return
            
        if not c:
            lbl_error.configure(text="Enter CAPTCHA")
            return

        if not p:
            lbl_error.configure(text="Password required")
            return

        if not re.match(r'^[A-Za-z0-9]+$', c):
            lbl_error.configure(
                text="CAPTCHA must contain English letters and numbers only"
            )
            return

        result["username"] = u
        result["password"] = p
        result["captcha"] = c

        root.destroy()

    login_btn = ctk.CTkButton(
        main,
        text="LOGIN",
        height=50,
        corner_radius=12,
        font=("Segoe UI", 15, "bold"),
        fg_color="#6B2D8E",
        hover_color="#4A1F63",
        command=submit
    )
    login_btn.pack(fill="x", padx=60, pady=(15, 10))

    ctk.CTkLabel(
        main,
        text="© Telecom Egypt - WE",
        text_color="gray",
        font=("Segoe UI", 10)
    ).pack(side="bottom", pady=10)

    root.bind("<Return>", submit)

    # إذا كانت نافذة فرعية، ننتظرها بدون mainloop كامل إذا كان الأب لديه واحد بالفعل
    if parent:
        parent.wait_window(root)
    else:
        root.mainloop()

    return result



def extract_captcha_image(driver, wait) -> bytes:
    img_elem = wait.until(
        EC.presence_of_element_located((By.XPATH, "//img[@alt='Captcha Code']"))
    )
    src = img_elem.get_attribute('src') or ""

    if src.startswith('data:image'):
        match = re.match(r'data:image/[^;]+;base64,\s*(.+)', src)
        if match:
            return base64.b64decode(match.group(1))
        raise ValueError("Failed to parse Base64 CAPTCHA image")

    import requests
    cookies = {c['name']: c['value'] for c in driver.get_cookies()}
    resp = requests.get(src, cookies=cookies, timeout=10)
    resp.raise_for_status()
    return resp.content


def is_captcha_error(driver) -> bool:
    try:
        error_elem = driver.find_element(
            By.XPATH,
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'captcha')]"
        )
        return error_elem.is_displayed()
    except Exception:
        return False


def is_login_error(driver) -> bool:
    try:
        error_elem = driver.find_element(
            By.XPATH,
            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'incorrect user') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'password')]"
        )
        return error_elem.is_displayed()
    except Exception:
        return False


def save_credentials(username: str, password: str):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"username": username, "password": password}, f, indent=2, ensure_ascii=False)


def load_credentials() -> tuple:
    if not os.path.exists(CONFIG_FILE):
        return "", ""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config.get('username', ''), config.get('password', '')


def save_row(row, file_path, log=print):
    df_row = pd.DataFrame([row])
    if os.path.exists(file_path):
        existing_df = pd.read_excel(file_path)
        updated_df = pd.concat([existing_df, df_row], ignore_index=True)
    else:
        updated_df = df_row
    updated_df.to_excel(file_path, index=False)
    order_id = row.get('KAM_Order') or row.get('New ORD') or ''
    log(f"Saved row for {order_id}")


def close_all_tabs(driver, log=print):
    while True:
        buttons = driver.find_elements(By.XPATH, "//span[contains(@class,'text-danger')]")
        if not buttons:
            break
        try:
            driver.execute_script('arguments[0].click();', buttons[-1])
            time.sleep(0.3)
        except Exception as e:
            log(f"Could not close tab: {e}")
            break


def perform_search(driver, wait, order):
    search_box = wait.until(
        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='KAM Order No']"))
    )
    search_box.clear()
    search_box.send_keys(str(order))
    search_btn = driver.find_element(By.XPATH, "//button[contains(text(),'Search')]")
    driver.execute_script("arguments[0].click();", search_btn)
    wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[contains(@class,'bg-light-grey')]//label")
        )
    )
    time.sleep(0.5)
    return driver.find_element(By.XPATH, "//div[contains(@class,'bg-light-grey')]")


def safe_search(driver, wait, order, retries=2, log=print):
    for attempt in range(retries):
        try:
            return perform_search(driver, wait, order)
        except Exception as e:
            log(f"Retry {attempt + 1} for {order} بسبب: {e}")
            driver.refresh()
            time.sleep(3)
            driver.execute_script(
                'arguments[0].click();',
                wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(.,'Find KAM Order No')]")))
            )
            driver.execute_script(
                'arguments[0].click();',
                wait.until(EC.visibility_of_element_located((By.XPATH, "//a[contains(text(),'FTTH KAMOrderNo')]")))
            )
    return None


def login(driver, username=None, password=None, wait_for_captcha=None, log=print):
    wait = WebDriverWait(driver, 20)
    driver.get(URL)
    
    # التأكد من أننا لسنا مسجلين دخول بالفعل لتجنب التكرار
    try:
        if driver.find_elements(By.CLASS_NAME, 'nav-toggle'):
            log("Already logged in, skipping login process.")
            return wait
    except:
        pass

    # Use provided credentials or load from config
    if isinstance(username, str) and isinstance(password, str) and username and password:
        saved_user, saved_pass = username, password
    else:
        saved_user, saved_pass = load_credentials()

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        log(f'Extracting CAPTCHA image (attempt {attempt}/{max_attempts})...')
        captcha_bytes = extract_captcha_image(driver, wait)

        log('Opening WE login window...')
        
        # التعامل مع طلب الواجهة من خيط خلفي (ECRM)
        is_main_thread = threading.current_thread() is threading.main_thread()
        if not is_main_thread and wait_for_captcha:
             result = wait_for_captcha(captcha_bytes, saved_user, saved_pass, attempt, max_attempts)
        else:
             result = show_login_captcha_popup(
                image_bytes=captcha_bytes,
                username_prefill=saved_user,
                password_prefill=saved_pass,
                attempt=attempt,
                max_attempts=max_attempts,
             )

        if not result or not result.get('captcha'):
            raise Exception("Login cancelled by user")

        username = result['username']
        password = result['password']
        captcha_code = result['captcha']

        if not os.path.exists(CONFIG_FILE) or username != saved_user or password != saved_pass:
            save_credentials(username, password)
            saved_user, saved_pass = username, password

        user_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
        user_field.clear()
        user_field.send_keys(username)
        # إرسال حدث لـ Angular ليفهم أن الحقل امتلأ
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", user_field)

        pass_field = driver.find_element(By.XPATH, "//input[@type='password']")
        pass_field.clear()
        pass_field.send_keys(password)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", pass_field)

        captcha_input = driver.find_element(By.XPATH, "//input[@formcontrolname='captchaCode']")
        captcha_input.clear()
        captcha_input.send_keys(captcha_code)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", captcha_input)

        # الانتظار حتى يختفي كلاس disabled من الزر
        login_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(),'Login')]")))
        wait.until(lambda d: "disabled" not in login_btn.get_attribute("class"))
        
        driver.execute_script("arguments[0].click();", login_btn)
        
        time.sleep(2.5)

        if is_captcha_error(driver):
            log("Invalid CAPTCHA! Retrying with new image...")
            try:
                close_btn = driver.find_element(
                    By.XPATH,
                    "//*[contains(@class,'close') or contains(@class,'swal2-close') or contains(@class,'toast-close')]"
                )
                close_btn.click()
                time.sleep(0.5)
            except Exception:
                pass
            time.sleep(1)
            continue

        if is_login_error(driver):
            raise Exception("Incorrect username or password!")

        try:
            # ننتظر ظهور عنصر القائمة الجانبية للتأكد من نجاح الدخول
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'nav-toggle')))
            break # نجاح الدخول، نخرج من دورة الـ Attempts
        except Exception:
            log("Login check failed, preparing next attempt...")
    else:
        raise Exception(f"Failed to login after {max_attempts} CAPTCHA attempts")

    try:
        nav_toggle = driver.find_element(By.CLASS_NAME, 'nav-toggle')
        driver.execute_script("arguments[0].click();", nav_toggle)
    except Exception:
        pass

    driver.execute_script(
        'arguments[0].click();',
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(.,'Find KAM Order No')]")))
    )
    driver.execute_script(
        'arguments[0].click();',
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(),'FTTH KAMOrderNo')]")))
    )
    return wait


def run_ftth_portal(
    input_file=DEFAULT_INPUT_FILE,
    output_file=DEFAULT_OUTPUT_FILE,
    log=print,
    username=None,
    password=None,
    wait_for_captcha=None
):
    # Check if input file exists, if not, ask the user to select one
    if not os.path.exists(input_file):
        log(f"⚠️ Default input file not found: {input_file}")
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected_file = filedialog.askopenfilename(
                title="Select Input Excel File (KAM Orders)",
                filetypes=[("Excel files", "*.xlsx *.xls")]
            )
            root.destroy()
            if not selected_file:
                log("❌ No file selected. Extraction cancelled.")
                return
            input_file = selected_file
        except Exception as e:
            log(f"❌ Error opening file dialog: {e}")
            return

    driver = create_chrome_driver()
    try:
        wait = login(driver, username=username, password=password, wait_for_captcha=wait_for_captcha, log=log)
        df = pd.read_excel(input_file)
        
        # Determine the order column name (KAM_Order or New ORD)
        order_col = next((c for c in ['KAM_Order', 'New ORD'] if c in df.columns), None)

        if not order_col:
            log("❌ Error: Column 'KAM_Order' or 'New ORD' not found in the selected Excel file!")
            return

        for order in df[order_col].dropna():
            log(f"Processing order: {order}")
            try:
                close_all_tabs(driver, log)
                container = safe_search(driver, wait, order, log=log)
                if container is None:
                    save_row({order_col: order, "Status": "Failed after retries"}, output_file, log=log)
                    continue
                row_data = {order_col: order}
                items = container.find_elements(By.XPATH, ".//div[contains(@class,'col-md-3')]")
                for item in items:
                    try:
                        key = item.find_element(By.TAG_NAME, 'label').text.strip()
                        value = item.find_element(By.TAG_NAME, 'p').text.strip()
                        row_data[key] = value if value else None
                    except Exception:
                        continue
                if len(row_data) == 1:
                    row_data['Status'] = 'No Data Found'
                save_row(row_data, output_file, log=log)
            except Exception as e:
                log(f"Fatal error with {order}: {e}")
                save_row({"KAM_Order": order, "Error": str(e)}, output_file, log=log)
        log('\nFinished successfully ✅')
    finally:
        driver.quit()


def ftth_main():
    run_ftth_portal()


if __name__ == '__main__':
    ftth_main()
