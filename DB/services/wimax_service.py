from selenium.webdriver.common.by import By

def open_wimax_page(driver):
    driver.get("http://172.29.29.108:8888/Wimaxdb/Details?type=tedata")


def fill_wimax(driver, row):
    def send(field_id, col):
        try:
            value = str(row.get(col, "")).strip()
            if value:
                el = driver.find_element(By.ID, field_id)
                el.clear()
                el.send_keys(value)
        except:
            pass

    send("OrderId", "Order Id")
    send("CustomerNumber", "Customer Number")
    send("CustomerName", "Customer Name")


def submit_wimax(driver):
    driver.find_element(By.XPATH, '//button[@type="submit"]').click()