from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from utils.mapping import get_sector_zone_from_msan
from selenium.webdriver.support.ui import Select

BASE_URL = "http://172.29.29.108:8888"
import time


from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def open_ftth_page(driver):
    wait = WebDriverWait(driver, 20)
    driver.maximize_window() # لضمان رؤية العناصر عند التشغيل من الـ Launcher

    current_url = driver.current_url

    # ✅ لو أنا بالفعل في صفحة Details → متعملش حاجة
    if "/FTTH/Details" in current_url:
        print("✅ Already in FTTH Details page → Skip opening menu")
        return

    # ===== 1. افتح menu =====
    ftth_menu = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//span[text()="FTTH"]'))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ftth_menu)
    driver.execute_script("arguments[0].click();", ftth_menu)

    # ===== 2. استنى collapse =====
    wait.until(
        EC.presence_of_element_located((By.ID, "collapseFTTH"))
    )
    time.sleep(0.5) # وقت بسيط لتمدد القائمة

    # ===== 3. اضغط FTTH List =====
    ftth_list = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//a[@href="/FTTH" and contains(@class,"collapse-item")]'))
    )
    driver.execute_script("arguments[0].click();", ftth_list)

    # ===== 4. استنى الصفحة =====
    # الانتظار حتى يصبح زر الـ Add مرئياً لضمان تحميل محتوى الصفحة بالكامل
    wait.until(EC.visibility_of_element_located((By.XPATH, '//a[contains(@href,"/FTTH/Details")]')))

    # ===== 5. اضغط Add =====
    add_btn = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//a[contains(@href,"/FTTH/Details")]'))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_btn)
    driver.execute_script("arguments[0].click();", add_btn)

    # تأكيد الانتقال للصفحة في حالة فشل الضغط الصامت عبر JS
    if "/FTTH/Details" not in driver.current_url:
        driver.execute_script("arguments[0].click();", add_btn)

    # ===== 6. استنى الفورم =====
    wait.until(EC.presence_of_element_located((By.ID, "OrderId")))



def set_input(driver, field_id, value):
    try:
        if value is not None and str(value).strip().lower() != "nan":
            el = driver.find_element(By.ID, field_id)

            driver.execute_script(
                "arguments[0].value = arguments[1];", el, str(value)
            )

    except Exception as e:
        print(f"❌ Input error ({field_id}): {value} → {e}")


def normalize(text):
    return str(text).strip().replace("  ", " ")

def set_select_by_text(driver, field_id, text):
    try:
        if not text:
            return

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, field_id))
        )

        select = Select(driver.find_element(By.ID, field_id))

        target = normalize(text)

        for option in select.options:
            opt_text = normalize(option.text)

            # 🔥 match مرن
            if target == opt_text or target in opt_text or opt_text in target:
                option.click()
                return

        print(f"⚠️ Not matched: {text}")
        print("Available options:")
        for o in select.options:
            print(f"- '{o.text}'")

    except Exception as e:
        print(f"❌ Select error ({field_id}): {text} → {e}")


from utils.mapping import get_sector_zone_from_msan


def fill_ftth(driver, row, logger=None):
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "OrderId"))
    )

    # ================= INPUT FIELDS =================
    mapping = {
    "Order Id": "OrderId",
    "Change Id": "ChangeId",
    "Change Name": "ChangeName",
    "Customer Number": "CustomerNO",
    "Customer Name": "CustomerName",
    "Branch": "Branch",
    "POP": "POPName",
    "MSAN Code": "MsanCode",   
    "MSAN IP": "MSANIP",
    "Vendor": "Vendor",
    "Old Cabinet": "OldCabinet",
    "Old MSAN IP": "OldMSANIP",
    "Old Port": "OldPort",
    "Old Circuit ID": "OldCircuitID",
    "New Circuit": "NewCircuit",
    "Shelf": "Shelf",
    "Card": "Card",
    "Port": "Port",
    "ONT": "ONT",
    "BSS Serial": "BSSSerial",
    "Contract Line": "ContractLine",
    "ONU Serial": "ONUSerial",
    "Old Ord": "OldOrd",
    "New Ord": "NewOrd",
    "WO Speed": "WoSpeed",
    "Comment": "NewComment"
}

    for col, field_id in mapping.items():
        set_input(driver, field_id, row.get(col))

  
    date_value = format_datetime_local(row.get("Migration Date"))

    if date_value:
        set_input(driver, "MigrationDate", date_value)

    # ================= SECTOR & ZONE (FROM MSAN ONLY) =================
    try:
        msan_code = str(row.get("MSAN Code", "")).strip()

        sector, zone = get_sector_zone_from_msan(msan_code)

        if logger:
            logger(f"🎯 Mapping: {msan_code} → {sector}, {zone}")

        if not sector or not zone:
            if logger:
                logger(f"❌ No mapping found for MSAN: {msan_code}")
            return

        # 🔥 مهم جدًا
        set_select_by_text(driver, "SectorId", sector)
        time.sleep(1)

        set_select_by_text(driver, "ZoneId", zone)

    except Exception as e:
        if logger:
            logger(f"⚠️ Sector/Zone error: {e}")

    # ================= SOURCE =================
    set_select_by_text(driver, "SourceId", row.get("Source"))

    # ================= Migration Status =================
    set_select_by_text(driver, "MsanShMigrationStatusId", row.get("Migration Status"))



def apply_sector_zone(driver, row, logger):
    try:
        msan_code = str(row.get("MSAN Code", "")).strip()

        sector, zone = get_sector_zone_from_msan(msan_code)

        if sector and zone:
            Select(driver.find_element(By.ID, "SectorId")).select_by_visible_text(sector)
            Select(driver.find_element(By.ID, "ZoneId")).select_by_visible_text(zone)

            logger(f"✅ FTTH MSAN {msan_code} → Sector: {sector}, Zone: {zone}")
        else:
            logger(f"⚠️ No mapping found for MSAN {msan_code}")

    except Exception as e:
        logger(f"⚠️ FTTH Sector/Zone error: {e}")


from datetime import datetime
from datetime import datetime

def format_datetime_local(value):
    try:
        if not value or str(value).strip().lower() == "nan":
            return None

        # 🔥 الحالة 1: pandas datetime
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%dT13:00")

        value_str = str(value).strip()

        # 🔥 الحالة 2: شكل pandas string
        if " " in value_str and "-" in value_str:
            dt = datetime.strptime(value_str, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%dT13:00")

        # 🔥 الحالة 3: Excel format القديم
        dt = datetime.strptime(value_str, "%m/%d/%Y")
        return dt.strftime("%Y-%m-%dT13:00")

    except Exception as e:
        print(f"❌ Date format error: {value} → {e}")
        return None
    


def submit_ftth(driver):
    wait = WebDriverWait(driver, 5)

    submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
    driver.execute_script("arguments[0].click();", submit_btn)

    try:
        # 🔥 استنى ظهور رسالة الخطأ
        error = wait.until(
            EC.presence_of_element_located((By.XPATH, '//p[contains(text(),"Problem")]'))
        )

        if error.is_displayed():
            print("❌ Save Failed (Popup Detected)")
            return False

    except:
        # مفيش error ظهر
        pass

    print("✅ Save Success")

    # Refresh
    driver.get(driver.current_url)
    wait.until(EC.presence_of_element_located((By.ID, "OrderId")))

    return True