from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
from utils.mapping import get_sector_zone_from_msan


class FiberService:

    def __init__(self, driver, log_func):
        self.driver = driver
        self.log = log_func

    # ================= OPEN PAGE =================
    def open_page(self):
        self.driver.get("http://172.29.29.108:8888/TedataCustomer/Details?type=fiber")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "OrderId"))
        )
        self.log("🌐 Opened Fiber Page")

    # ================= DATE FORMAT =================
    def set_date_js(self, id_, value):
        try:
            if value:
                self.driver.execute_script(
                    f'document.getElementById("{id_}").value = "{value}";'
                )
        except Exception as e:
            self.log(f"⚠️ Failed setting date {id_}: {e}")

    def format_date(self, val):
        try:
            dt = pd.to_datetime(val, dayfirst=False)
            return dt.strftime("%Y-%m-%d")
        except Exception as e:
            self.log(f"⚠️ Date error: {val} → {e}")
            return ""

    # ================= SAFE SEND =================
    def safe_send(self, id_, value):
        try:
            if pd.notna(value):
                # تحويل القيمة إلى نص
                value_str = str(value)
                # إذا كانت القيمة عبارة عن رقم عشري (float) ينتهي بـ .0، يتم تحويله إلى رقم صحيح
                if isinstance(value, float) and value.is_integer():
                    value_str = str(int(value))

                el = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, id_))
                )
                el.clear()
                el.send_keys(value_str)
        except Exception as e:
            self.log(f"⚠️ Failed sending {id_}: {e}")
    

    def first_existing_id(self, ids, timeout=2):
        try:
            return WebDriverWait(self.driver, timeout).until(
                lambda d: next((id_ for id_ in ids if d.find_elements(By.ID, id_)), None)
            )
        except Exception:
            return None

    def safe_send_any(self, ids, value, label):
        if not pd.notna(value):
            return

        field_id = self.first_existing_id(ids)
        if not field_id:
            self.log(f"Field not found for {label}: {', '.join(ids)}")
            return

        self.safe_send(field_id, value)

    # ================= SMART SELECT =================
    def safe_select(self, id_, value):
        try:
            if pd.notna(value):

                select = Select(WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, id_))
                ))

                value = str(value).strip().lower()

                for option in select.options:
                    if value in option.text.lower():
                        select.select_by_visible_text(option.text)
                        return

                self.log(f"⚠️ Value '{value}' not found in {id_}")

        except Exception as e:
            self.log(f"⚠️ Failed selecting {id_}: {e}")

    def safe_select_any(self, ids, value, label):
        if not pd.notna(value):
            return

        field_id = self.first_existing_id(ids)
        if not field_id:
            self.log(f"Select not found for {label}: {', '.join(ids)}")
            return

        self.safe_select(field_id, value)

    # ================= FILL FORM =================
    def fill_form(self, row):

        # ===== BASIC =====
        self.safe_send("OrderId", row.get("Order Id"))
        self.safe_send("CustomerNumber", row.get("Customer Number"))
        self.safe_send("Name", row.get("Customer Name"))
        self.safe_send("BranchName", row.get("Branch Name"))
        self.safe_send("Vendor", row.get("Vendor"))

        # ===== CHANGE =====
        self.safe_send("ChangeId", row.get("ChangeId"))
        self.safe_send("CabinetName", row.get("Cabinet"))
        self.safe_send("Popname", row.get("POP"))

        # ===== DROPDOWNS =====
        self.safe_select("statusId", row.get("State"))
        self.safe_select("MsanstatusId", row.get("MSAN Status"))
        self.safe_select("CutreasonId", row.get("Cut Reason"))
        self.safe_select("SourceId", row.get("Source"))

        # ===== SECTOR & ZONE AUTO =====
        try:
            msan_code = row.get("MSAN Code")
            sector, zone = get_sector_zone_from_msan(msan_code)

            self.log(f"🎯 Mapping: {msan_code} → {sector}, {zone}")

            if sector:
                self.safe_select("SectorID", sector)

                WebDriverWait(self.driver, 10).until(
                    lambda d: len(Select(d.find_element(By.ID, "ZoneId")).options) > 1
                )

                if zone:
                    self.safe_select("ZoneId", zone)

        except Exception as e:
            self.log(f"⚠️ Sector/Zone error: {e}")

        # ===== NETWORK =====
        self.safe_send("Olddslamname", row.get("Old Switch Name"))
        self.safe_send("Olddslamip", row.get("Old Switch IP"))
        self.safe_send("MsanIp", row.get("MSAN IP"))
        self.safe_send("MsanCode", row.get("MSAN Code"))

        # ===== DATES (🔥 FIXED) =====
        act_date = self.format_date(row.get("Activation Date"))
        mov_date = self.format_date(row.get("Movement Date"))

        self.set_date_js("ActivationDate", act_date)
        self.set_date_js("MovementDate", mov_date)

        # ===== COMMENT =====
        self.safe_send("Comment", row.get("Comment"))

        # ===== CIRCUIT =====
        try:
            self.safe_send_any(["cidm0", "cidm", "cidm1"], row.get("Circuit ID"), "Circuit ID")

            self.safe_select_any(["cs0", "cs1"], row.get("Circuit Status") or "Not Moved", "Circuit Status")
            self.safe_select_any(["mr0", "mr1"], row.get("Not Moved Reason") or "N/A", "Not Moved Reason")

            self.safe_send_any(["ncs0", "ncs1"], row.get("Circuit Shelf"), "Circuit Shelf")
            self.safe_send_any(["ncc0", "ncc1"], row.get("Circuit Card"), "Circuit Card")
            self.safe_send_any(["ncp0", "cp0", "ncp1", "cp1"], row.get("Circuit Port"), "Circuit Port")

            # 🔥 FIXED (accept ESFP / csfp etc)
            self.safe_select_any(["ce0", "ce1"], row.get("Cabinet SFP") or "ESFP", "Cabinet SFP")
            self.safe_select_any(["cse0", "cse1"], row.get("CST SFP") or "ESFP", "CST SFP")

        except Exception as e:
            self.log(f"⚠️ Circuit error: {e}")

        self.log("✅ Fiber form filled")

    # ================= SUBMIT =================
    def submit(self):
        try:
            btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]'))
            )
            btn.click()

            # 🔥 wait success popup
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "success"))
            )

            self.log("💾 Fiber Saved Successfully")

        except Exception as e:
            self.log(f"❌ Save failed: {e}")
    

    
