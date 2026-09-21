from types import SimpleNamespace

from ecrm_extractor.cancellation import check_cancelled
from ecrm_extractor.core.api_client import (
    download_pdf,
    get_account_full_json,
    get_documents_by_resource,
    get_installed_base,
    get_commercial_order_lines,
    get_notes_by_document,
    get_port_full_data,
    get_product_flats,
    get_resource_by_cid,
    get_resources_by_cids,
    get_resource_full_data,
    get_resources,
    get_notes,
    get_resources_by_ord,
    get_service_order_by_soid,
    get_service_orders,
    get_tasks,
    get_user_full_json,
    get_child_service_orders,
    get_resources_by_service_order,
    get_service_order_components,
)

# استيراد منطق البورتال من المشروع المجاور
import sys
import time
import threading
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from ecrm_extractor.core.session import create_session, save_credentials
from ecrm_extractor.domain.extractors import (
    enrich_installed_with_speed,
    extract_full_data,
    extract_hardware,
    extract_l3_data,
    extract_nid,
    extract_old_new_from_so,
    extract_order_status_from_ib,
    extract_speed,
    get_latest_commercial_so,
    get_latest_data_services_so,
    get_latest_migration_esupport_so,
    get_pdfs_from_notes,
    get_text,
    filter_by_so,
)


def _clean_key(value):
    return str(value).strip()


def _cached(cache, key, loader, default):
    key = _clean_key(key)
    if not key:
        return default
    if key not in cache:
        cache[key] = loader(key)
    return cache[key]


# مخزن مؤقت عالمي يستمر طوال فترة تشغيل التطبيق لمنع تكرار الاستخراج
_GLOBAL_CACHED_DATA = {
    "accounts": {},
    "cid_resources": {},
    "documents": {},
    "installed_base": {},
    "commercial_order_lines": {},
    "notes": {},
    "ord_resources": {},
    "ports": {},
    "product_flats": {},
    "resource_full": {},
    "resources": {},
    "service_order_by_soid": {},
    "service_orders": {},
    "tasks": {},
    "users": {},
    "child_service_orders": {},
    "so_resources": {},
}

def build_extraction_dependencies(gui_context):
    caches = _GLOBAL_CACHED_DATA
    ftth_cache = {"module": None, "driver": None, "wait": None, "lock": threading.Lock()}

    def cached_get_account_full_json(session, account_id):
        return _cached(
            caches["accounts"],
            account_id,
            lambda key: get_account_full_json(session, key),
            {},
        )

    def cached_get_documents_by_resource(session, rr_id):
        return _cached(
            caches["documents"],
            rr_id,
            lambda key: get_documents_by_resource(session, key),
            [],
        )

    def cached_get_installed_base(session, order):
        return _cached(
            caches["installed_base"],
            order,
            lambda key: get_installed_base(session, key),
            [],
        )
    def cached_get_commercial_order_lines(session, order):
        return _cached(
            caches["commercial_order_lines"],
            order,
            lambda key: get_commercial_order_lines(session, key),
            [],
        )
    def cached_get_notes_by_document(session, activity_id):
        return _cached(
            caches["notes"],
            activity_id,
            lambda key: get_notes_by_document(session, key),
            [],
        )

    def cached_get_notes(session, entity_id):
        return _cached(
            caches["notes"],
            entity_id,
            lambda key: get_notes(session, key),
            [],
        )

    def cached_get_port_full_data(session, port_id):
        return _cached(
            caches["ports"],
            port_id,
            lambda key: get_port_full_data(session, key),
            {},
        )

    def cached_get_product_flats(session, product_flat_ids):
        product_flat_ids = {
            _clean_key(product_flat_id)
            for product_flat_id in product_flat_ids
            if product_flat_id
        }
        missing_ids = {
            product_flat_id
            for product_flat_id in product_flat_ids
            if product_flat_id not in caches["product_flats"]
        }

        if missing_ids:
            caches["product_flats"].update(get_product_flats(session, missing_ids))

        return {
            product_flat_id: caches["product_flats"].get(product_flat_id, {})
            for product_flat_id in product_flat_ids
        }

    def cached_get_resource_by_cid(session, cid):
        return _cached(
            caches["cid_resources"],
            cid,
            lambda key: get_resource_by_cid(session, key),
            [],
        )

    def cached_get_resources_by_cids(session, cid_values):
        clean_cids = tuple(
            dict.fromkeys(
                _clean_key(cid)
                for cid in cid_values
                if _clean_key(cid)
            )
        )
        missing_cids = [
            cid
            for cid in clean_cids
            if cid not in caches["cid_resources"]
        ]

        if missing_cids:
            grouped = {cid: [] for cid in missing_cids}

            for i in range(0, len(missing_cids), 20):
                check_cancelled(gui_context)
                resources = get_resources_by_cids(session, missing_cids[i:i + 20])

                for resource in resources:
                    cid = _clean_key(resource.get("te_circuitid"))
                    if cid in grouped:
                        grouped[cid].append(resource)

            caches["cid_resources"].update(grouped)

        results = []
        for cid in clean_cids:
            results.extend(caches["cid_resources"].get(cid, []))

        return results

    def cached_get_resource_full_data(session, rr_id):
        return _cached(
            caches["resource_full"],
            rr_id,
            lambda key: get_resource_full_data(session, key),
            {},
        )

    def cached_get_resources(session, order):
        return _cached(
            caches["resources"],
            order,
            lambda key: get_resources(session, key),
            [],
        )

    def cached_get_resources_by_ord(session, ord_number):
        return _cached(
            caches["ord_resources"],
            ord_number,
            lambda key: get_resources_by_ord(session, key),
            [],
        )

    def cached_get_service_order_by_soid(session, so_id):
        return _cached(
            caches["service_order_by_soid"],
            so_id,
            lambda key: get_service_order_by_soid(session, key),
            [],
        )

    def cached_get_service_orders(session, order):
        return _cached(
            caches["service_orders"],
            order,
            lambda key: get_service_orders(session, key),
            [],
        )

    def cached_get_tasks(session, so_id, child_so_ids=None):

        cache_key = (
            str(so_id),
            tuple(sorted(child_so_ids or []))
        )

        return _cached(
            caches["tasks"],
            cache_key,
            lambda _: get_tasks(
                session,
                so_id,
                child_so_ids
            ),
            [],
        )

    def cached_get_user_full_json(session, user_id):
        return _cached(
            caches["users"],
            user_id,
            lambda key: get_user_full_json(session, key),
            {},
        )
    def cached_get_child_service_orders(session, so_id):
        return _cached(
            caches["child_service_orders"],
            so_id,
            lambda key: get_child_service_orders(session, key),
            [],
        )
    
    def cached_get_resources_by_service_order(session, so_id):
        return _cached(
            caches["so_resources"],
            so_id,
            lambda key: get_resources_by_service_order(session, key),
            [],
        )
    def cached_get_service_order_components(session, so_id):
        return _cached(
            caches["so_resources"],
            so_id,
            lambda key: get_service_order_components(session, key),
            [],
        )

    def fetch_ftth_portal_data(ord_number, gui=None):
        """
        تكامل مع Selenium الخاص بـ FTTH Portal لجلب البيانات التقنية.
        """
        with ftth_cache["lock"]:
            try:
                # الكاش لمنع إعادة تحميل الموديول مع كل صف
                if ftth_cache["module"] is None:
                    import importlib.util
                    portal_path = (
                        Path(__file__).resolve().parent.parent.parent
                        / "FTTH portal"
                        / "ftth_we_portal.py"
                    )

                    spec = importlib.util.spec_from_file_location(
                        "ftth_portal_main",
                        str(portal_path)
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    ftth_cache["module"] = module

                ftth_main = ftth_cache["module"]

                # التحقق من وجود درايفر نشط أو إنشاء واحد جديد
                driver = ftth_cache.get("driver")
                if driver is None:
                    driver = ftth_main.create_chrome_driver(headless=True)
                    ftth_cache["driver"] = driver

                try:
                    # استخدام واجهة الدخول الأصلية الخاصة بالبورتال
                    def invoke_portal_gui(captcha_bytes, user, pw, attempt, total):
                        if not (gui and hasattr(gui, "root")): return None
                        res_container = {"data": None}
                        done_event = threading.Event()
                        def run_on_main():
                            res_container["data"] = ftth_main.show_login_captcha_popup(
                                captcha_bytes, user, pw, attempt, total, parent=gui.root
                            )
                            done_event.set()
                        gui.root.after(0, run_on_main)
                        done_event.wait()
                        return res_container["data"]

                    wait = ftth_main.login(
                        driver, 
                        username=None,
                        password=None,
                        wait_for_captcha=invoke_portal_gui,
                        log=print
                    )
                    ftth_cache["wait"] = wait
                    
                    # تأمين الانتقال لصفحة البحث في كل مرة لضمان نظافة الصفحة
                    try:
                        driver.execute_script(
                            'arguments[0].click();',
                            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(.,'Find KAM Order No')]")))
                        )
                        driver.execute_script(
                            'arguments[0].click();',
                            wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(),'FTTH KAMOrderNo')]")))
                        )
                    except: pass

                    container = ftth_main.safe_search(driver, wait, ord_number, log=print)
                    if container:
                        # زيادة وقت الانتظار قليلاً لضمان اكتمال تحميل الـ DOM الخاص ببيانات الـ ONT
                        time.sleep(3.0)
                        
                        # البحث عن جميع الأعمدة التقنية داخل الحاوية
                        items = container.find_elements(
                            ftth_main.By.XPATH,
                            ".//div[contains(@class,'col-md-3')]"
                        )

                        result = {}
                        for item in items:
                            try:
                                # استخراج المسمى (Label)
                                labels = item.find_elements(ftth_main.By.TAG_NAME, "label")
                                if not labels: continue
                                key = labels[0].text.strip()
                                
                                # محاولة استخراج القيمة من p أو span أو div داخلي
                                val = ""
                                for tag in ["p", "span", "strong", "div"]:
                                    elements = item.find_elements(ftth_main.By.TAG_NAME, tag)
                                    if elements and elements[0].text.strip() and elements[0].text.strip() != key:
                                        val = elements[0].text.strip()
                                        break
                                
                                if key: result[key] = val
                            except Exception: continue
                        return result

                    return {}
                except Exception as e:
                    # في حالة حدوث خطأ فادح في المتصفح، نقوم بإغلاقه لتنظيف الجلسة
                    if "driver" in ftth_cache and ftth_cache["driver"]:
                        try:
                            ftth_cache["driver"].quit()
                        except: pass
                        ftth_cache["driver"] = None
                    return f"Error: {str(e)}"
            except Exception as e:
                return f"Error: {str(e)}"

    # إضافة تنظيف للمتصفح عند الانتهاء من كافة العمليات (اختياري)
    def cleanup_ftth():
        with ftth_cache["lock"]:
            if ftth_cache.get("driver"):
                ftth_cache["driver"].quit()
                ftth_cache["driver"] = None

    return SimpleNamespace(
        create_session=lambda: create_session(
            gui_context.username,
            gui_context.password,
        ),
        save_credentials=save_credentials,
        get_resource_by_cid=cached_get_resource_by_cid,
        get_resources_by_cids=cached_get_resources_by_cids,
        get_service_orders=cached_get_service_orders,
        get_service_order_by_soid=cached_get_service_order_by_soid,
        get_latest_commercial_so=get_latest_commercial_so,
        get_latest_migration_esupport_so=get_latest_migration_esupport_so,
        get_latest_data_services_so=get_latest_data_services_so,
        get_tasks=cached_get_tasks,
        get_child_service_orders=cached_get_child_service_orders,
        get_resources=cached_get_resources,
        get_installed_base=cached_get_installed_base,
        get_commercial_order_lines=cached_get_commercial_order_lines,
        extract_hardware=extract_hardware,
        get_product_flats=cached_get_product_flats,
        enrich_installed_with_speed=enrich_installed_with_speed,
        extract_old_new_from_so=extract_old_new_from_so,
        extract_full_data=extract_full_data,
        get_account_full_json=cached_get_account_full_json,
        get_user_full_json=cached_get_user_full_json,
        get_text=get_text,
        extract_speed=extract_speed,
        extract_order_status_from_ib=extract_order_status_from_ib,
        extract_nid=extract_nid,
        get_resource_full_data=cached_get_resource_full_data,
        get_notes_by_document=cached_get_notes_by_document,
        get_notes=cached_get_notes,
        get_documents_by_resource=cached_get_documents_by_resource,
        get_pdfs_from_notes=get_pdfs_from_notes,
        download_pdf=download_pdf,
        extract_l3_data=extract_l3_data,
        get_port_full_data=cached_get_port_full_data,
        get_resources_by_ord=cached_get_resources_by_ord,
        filter_by_so=filter_by_so,
        get_resources_by_service_order=get_resources_by_service_order,
        get_service_order_components=cached_get_service_order_components,
        fetch_ftth_portal_data=fetch_ftth_portal_data,
        cleanup_ftth=cleanup_ftth,
    )
