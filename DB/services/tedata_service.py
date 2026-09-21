from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = "http://172.29.29.108:8888"


def open_search_page(driver):
    driver.get(f"{BASE_URL}/TedataCustomer")


def open_fiber_search_page(driver):
    driver.get(f"{BASE_URL}/TedataCustomer?type=fiber")


def _search_datatable(driver, value):
    wait = WebDriverWait(driver, 10)
    search_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="search"]'))
    )
    search_input.clear()
    search_input.send_keys(str(value))

    wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#groupsdatatable tbody tr"))
    )


def search_by_cid(driver, cid):
    _search_datatable(driver, cid)


def search_by_order_id(driver, order_id):
    _search_datatable(driver, order_id)


def open_edit_page(driver):
    edit_btn = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.EditGroupBtn'))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", edit_btn)
    driver.execute_script("arguments[0].click();", edit_btn)


def validate_row(driver, row, df, idx, logger, check_map):
    cid = str(row.get("Circuit ID", "")).strip()

    open_search_page(driver)
    search_by_cid(driver, cid)

    try:
        open_edit_page(driver)
        logger(f"✅ CID {cid} exists")
        df.at[idx, "CID Status"] = "Exists"
    except:
        logger(f"❌ CID {cid} not found")
        df.at[idx, "CID Status"] = "Not Found"
        return

    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.ID, "MsanIp")))

    for field_id in ["MsanIp", "ncs0", "ncc0", "ncp0"]:
        try:
            val = driver.find_element(By.ID, field_id).get_attribute("value").strip()
            df.at[idx, check_map[field_id]] = "YES" if val else "NO"
        except:
            df.at[idx, check_map[field_id]] = "NOT FOUND"


def update_row(driver, row, logger, selected_fields):
    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.ID, "Name")))

    def update(field_id, value):
        try:
            if value:
                el = driver.find_element(By.ID, field_id)
                el.clear()
                el.send_keys(value)
        except:
            logger(f"⚠️ Failed updating {field_id}")

    if "Customer Name" in selected_fields:
        update("Name", row.get("Customer Name"))

    if "Customer Number" in selected_fields:
        update("CustomerNumber", row.get("Customer Number"))

    if "MsanIp" in selected_fields:
        update("MsanIp", row.get("MsanIp"))

    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
    logger("💾 Updated")
