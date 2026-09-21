from ecrm_extractor.domain.pdf import find_work_order_pdf
import re
import os
import importlib.util
from pathlib import Path


def add_customer_name(row, ctx):
    deps = ctx["deps"]
    so = ctx.get("so")
    installed = ctx.get("installed", [])
    
    # 1. Attempt retrieval from Service Order (Latest)
    name = deps.get_text(so, "_te_customernameaccountid_value")
    
    # 2. Fallback to Installed Base (CID case without order)
    if not name and installed:
        for item in installed:
            name = item.get("_customerid_value@OData.Community.Display.V1.FormattedValue")
            if name: break
            
    row["CST Name"] = name or ""


def add_branch(row, ctx):
    deps = ctx["deps"]
    so = ctx.get("so")
    installed = ctx.get("installed", [])
    
    branch = deps.get_text(so, "_te_branchnameaccountid_value")
    
    if not branch and installed:
        for item in installed:
            branch = item.get("_te_branchaccountid_value@OData.Community.Display.V1.FormattedValue")
            if branch: break
            
    row["Branch"] = branch or ""


def add_pop(row, ctx):
    deps = ctx["deps"]
    so = ctx.get("so", {})
    pop = deps.get_text(so, "te_popnamev")

    if not pop:
        for item in ctx.get("service_orders", []):
            pop = deps.get_text(item, "te_popnamev")
            if pop:
                break

    if not pop:
        for resource in ctx.get("resources", []):
            pop = resource.get(
                "_te_poplistid_value@OData.Community.Display.V1.FormattedValue",
                "",
            )
            if pop:
                break

    row["POP"] = pop or "No POP"


def add_speed(row, ctx):
    installed = ctx.get("installed", []) or []
    
    # 1. Filter for Active records that are not hardware and have speed data
    active_with_speed = [
        x for x in installed
        if (
            x.get("statuscode@OData.Community.Display.V1.FormattedValue") == "Active"
            and x.get("te_producttypecode") != 2
            and (x.get("_speed") or x.get("_product_flat", {}).get("te_speed"))
            and "No Speed" not in str(x.get("_speed") or x.get("_product_flat", {}).get("te_speed", ""))
        )
    ]

    if active_with_speed:
        # 2. Choose the latest record based on creation date
        latest_active = max(active_with_speed, key=lambda x: x.get("createdon") or "")
        speed_text = latest_active.get("_speed") or latest_active.get("_product_flat", {}).get("te_speed", "")
        row["Speed"] = speed_text
    else:
        # 3. Old logic fallback if no clear active records
        row["Speed"] = ctx["deps"].extract_speed(installed)



def add_order_status(row, ctx):
    """
    Order Status is determined from Commercial Order Service Lines.

    Rules:
    - Order not found -> not found
    - No commercial lines -> order not exist
    - Service records only
    - Newest Service is checked first
    - Sale Suspension -> Sale Suspension
    - Sales Termination -> Terminated
    - Fulfilled / FullFilled -> Active
    - InFlight / Canceled -> skip and check previous Service
    - Any other status -> Active
    """

    order = str(ctx.get("order") or "").strip()
    commercial_lines = ctx.get("commercial_lines", []) or []

    # =====================================================
    # 1. ORDER NOT FOUND
    # =====================================================

    if not order:
        row["Order Status"] = "not found"
        return

    # =====================================================
    # 2. ORDER EXISTS BUT NO COMMERCIAL LINES
    # =====================================================

    if not commercial_lines:
        row["Order Status"] = "order not exist"
        return

    # =====================================================
    # 3. SERVICE RECORDS ONLY
    # =====================================================

    service_lines = []

    for item in commercial_lines:

        product_type = str(
            item.get(
                "te_producttypecode@OData.Community.Display.V1.FormattedValue"
            )
            or item.get(
                "te_producttype@OData.Community.Display.V1.FormattedValue"
            )
            or item.get("te_producttype")
            or ""
        ).strip().lower()

        if product_type == "service":
            service_lines.append(item)

    # =====================================================
    # 4. NO SERVICE ORDER
    # =====================================================

    if not service_lines:
        row["Order Status"] = "order not exist"
        return

    # =====================================================
    # 5. SORT NEWEST -> OLDEST
    # =====================================================

    service_lines.sort(
        key=lambda x: (
            x.get("createdon")
            or x.get("modifiedon")
            or ""
        ),
        reverse=True
    )

    # =====================================================
    # 6. CHECK SERVICE ORDERS
    # =====================================================

    for item in service_lines:

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        status = str(
            item.get(
                "te_serviceorderstatuscode@OData.Community.Display.V1.FormattedValue"
            )
            or item.get(
                "te_statuscode@OData.Community.Display.V1.FormattedValue"
            )
            or item.get(
                "statuscode@OData.Community.Display.V1.FormattedValue"
            )
            or ""
        ).strip().lower()

        # -------------------------------------------------
        # ORDER TYPE
        # -------------------------------------------------

        order_type = str(
            item.get(
                "te_ordertypecode@OData.Community.Display.V1.FormattedValue"
            )
            or item.get(
                "te_ordertype@OData.Community.Display.V1.FormattedValue"
            )
            or ""
        ).strip().lower()

        # =================================================
        # SALE SUSPENSION
        # =================================================
        #
        # IMPORTANT:
        #
        # If the latest Service Order is:
        #
        # Order Type = Sale Suspension
        # Status     = FullFilled
        #
        # Result MUST be:
        #
        # Sale Suspension
        #
        # Do NOT check FullFilled before this condition.
        # =================================================

        if (
            "sale suspension" in order_type
            or "sales suspension" in order_type
        ):
            row["Order Status"] = "Sale Suspension"
            return

        # =================================================
        # SALES TERMINATION
        # =================================================

        if "sales termination" in order_type:
            row["Order Status"] = "Terminated"
            return

        # =================================================
        # IGNORE INFLIGHT / CANCELED
        # =================================================

        if status in {
            "inflight",
            "in flight",
            "canceled",
            "cancelled",
        }:
            continue

        # =================================================
        # FULFILLED
        # =================================================

        if status in {
            "fulfilled",
            "fullfilled",
        }:
            row["Order Status"] = "Active"
            return

        # =================================================
        # ANY OTHER STATUS
        # =================================================

        row["Order Status"] = "Active"
        return

    # =====================================================
    # ALL SERVICE ORDERS WERE INFLIGHT / CANCELED
    # =====================================================

    row["Order Status"] = "not found"
    

def add_circuit_status(row, ctx):
    """
    Circuit Status:
        Active
        Inactive
        not found

    Priority:
    1. New Circuit ID
    2. Old Circuit ID
    3. Input CID
    4. Circuit linked to Order (new_orderlinenumberid)
    """

    resources = (
        ctx.get("resources")
        or ctx.get("cid_resources")
        or []
    )

    result = ctx.get("result") or {}

    # =====================================================
    # 1) GET CIRCUIT IDS FROM RESULT
    # =====================================================

    new_cid = str(
        result.get("New Circuit ID") or ""
    ).strip()

    old_cid = str(
        result.get("Old Circuit ID") or ""
    ).strip()

    input_cid = str(
        ctx.get("input_cid") or ""
    ).strip()

    # =====================================================
    # 2) BUILD CID LIST
    # =====================================================

    candidate_cids = []

    for cid in [new_cid, old_cid, input_cid]:
        if cid and cid not in candidate_cids:
            candidate_cids.append(cid)

    # =====================================================
    # 3) IF ORDER MODE AND NO CID FOUND
    #    FIND CIRCUIT USING ORDER NUMBER
    # =====================================================

    order = str(
        ctx.get("order") or ""
    ).strip()

    if order and resources:
        for r in resources:

            order_line = str(
                r.get("new_orderlinenumberid") or ""
            ).strip()

            cid = str(
                r.get("te_circuitid") or ""
            ).strip()

            if (
                order_line == order
                and cid
                and cid not in candidate_cids
            ):
                candidate_cids.append(cid)

    # =====================================================
    # 4) FIND MATCHING RESOURCE
    # =====================================================

    matched_resources = []

    if candidate_cids:

        for r in resources:

            cid = str(
                r.get("te_circuitid") or ""
            ).strip()

            if cid in candidate_cids:
                matched_resources.append(r)

    # =====================================================
    # 5) FALLBACK
    # =====================================================

    if not matched_resources:

        row["Circuit Status"] = "not found"
        return

    # =====================================================
    # 6) LATEST RESOURCE
    # =====================================================

    latest = max(
        matched_resources,
        key=lambda r: (
            r.get("modifiedon")
            or r.get("createdon")
            or ""
        )
    )

    # =====================================================
    # 7) STATECODE = SOURCE OF TRUTH
    # =====================================================

    state = latest.get("statecode")

    if state == 0:
        row["Circuit Status"] = "Active"

    elif state == 1:
        row["Circuit Status"] = "Inactive"

    else:
        status = latest.get("statuscode")

        if status == 1:
            row["Circuit Status"] = "Active"

        elif status == 2:
            row["Circuit Status"] = "Inactive"

        else:
            row["Circuit Status"] = "not found"

            
def _get_latest_service_product(installed):
    """
    Extract the latest Service Product from Installed Base.

    Product type priority:
        1. te_producttypecode@OData.Community.Display.V1.FormattedValue
        2. _product_flat.te_producttypecode@OData.Community.Display.V1.FormattedValue
        3. _product_flat.te_producttype

    Product priority:
        1. _productid_value@OData.Community.Display.V1.FormattedValue
        2. _product_flat._te_productid_value@OData.Community.Display.V1.FormattedValue

    Selection priority:
        1. Active Service records
        2. If no Active Service exists, all Service records

    The second stage is important because some valid Service records can
    have a non-Active state while still containing a valid Product.
    """

    installed = installed or []

    def is_service(item):
        # =====================================================
        # PRIMARY SERVICE TYPE
        # =====================================================
        product_type = str(
            item.get(
                "te_producttypecode@OData.Community.Display.V1.FormattedValue",
                ""
            )
            or ""
        ).strip().lower()

        if product_type == "service":
            return True

        # =====================================================
        # FALLBACK: PRODUCT FLAT
        # =====================================================
        product_flat = item.get("_product_flat") or {}

        flat_product_type = str(
            product_flat.get(
                "te_producttypecode@OData.Community.Display.V1.FormattedValue",
                ""
            )
            or product_flat.get("te_producttype")
            or ""
        ).strip().lower()

        return flat_product_type == "service"

    def get_product(item):
        # =====================================================
        # PRIMARY PRODUCT SOURCE
        # =====================================================
        product = str(
            item.get(
                "_productid_value@OData.Community.Display.V1.FormattedValue",
                ""
            )
            or ""
        ).strip()

        if product:
            return product

        # =====================================================
        # FALLBACK: PRODUCT FLAT
        # =====================================================
        product_flat = item.get("_product_flat") or {}

        product = str(
            product_flat.get(
                "_te_productid_value@OData.Community.Display.V1.FormattedValue",
                ""
            )
            or ""
        ).strip()

        return product

    # =========================================================
    # 1. COLLECT ALL SERVICE RECORDS
    # =========================================================
    service_records = [
        item
        for item in installed
        if is_service(item)
    ]

    if not service_records:
        return ""

    # =========================================================
    # 2. PREFER ACTIVE SERVICE RECORDS
    # =========================================================
    active_services = [
        item
        for item in service_records
        if (
            item.get("statecode") == 0
            or str(
                item.get(
                    "statecode@OData.Community.Display.V1.FormattedValue",
                    ""
                )
                or ""
            ).strip().lower() == "active"
            or str(
                item.get(
                    "statuscode@OData.Community.Display.V1.FormattedValue",
                    ""
                )
                or ""
            ).strip().lower() == "active"
        )
    ]

    candidates = active_services or service_records

    # =========================================================
    # 3. LATEST FIRST
    # =========================================================
    candidates = sorted(
        candidates,
        key=lambda x: (
            x.get("createdon")
            or x.get("modifiedon")
            or ""
        ),
        reverse=True
    )

    # =========================================================
    # 4. RETURN FIRST SERVICE THAT HAS A PRODUCT
    # =========================================================
    for item in candidates:
        product = get_product(item)

        if product:
            return product

    return ""


def _extract_transmission_media(product):
    match = re.search(r"\bover\s+(\S+)", str(product or ""), flags=re.IGNORECASE)
    if not match:
        return ""

    return match.group(1).strip(" ,;|-/")


def add_product(row, ctx):

    installed = ctx.get("installed", [])
    selected = ctx.get("selected", set())

    # =====================================================
    # PRODUCT
    # =====================================================
    if "Product" in selected:
        row["Product"] = _get_latest_service_product(installed)

    # =====================================================
    # HARDWARE
    # =====================================================
    if "Hardware" in selected:

        active_hardware = [
            x for x in installed
            if (
                x.get(
                    "statuscode@OData.Community.Display.V1.FormattedValue",
                    ""
                ) == "Active"

                and

                x.get("_product_flat", {}).get("te_producttype") == "Hardware"
            )
        ]

        if active_hardware:
            hw_items = []
            # Order hardware from latest to oldest
            sorted_hw = sorted(
                active_hardware,
                key=lambda x: x.get("createdon") or "",
                reverse=True
            )
            
            for hw in sorted_hw:
                name = hw.get("_productid_value@OData.Community.Display.V1.FormattedValue", "")
                sale_type = hw.get("te_hardwaresaletypecode@OData.Community.Display.V1.FormattedValue", "")
                
                if name:
                    # Merge name with sales type
                    full_str = f"{name} | {sale_type}" if sale_type else name
                    hw_items.append(full_str)
            
            # Join all found hardware items
            row["Hardware"] = " - ".join(hw_items)

        else:
            row["Hardware"] = ""


def add_transmission_media(row, ctx):
    product = row.get("Product") or _get_latest_service_product(ctx.get("installed", []))
    media = _extract_transmission_media(product)
    
    # Improve GPON detection if traditional Regex fails
    if not media and product and "GPON" in str(product).upper():
        media = "GPON"
        
    # تحسين اكتشاف Fiber
    if not media and product and "FIBER" in str(product).upper():
        media = "Fiber"
        
    row["Transmission Type"] = media or ""
            
def add_cid(row, ctx):

    result = ctx["result"]

    old_cid = result.get("Old Circuit ID", "")
    new_cid = result.get("New Circuit ID", "")

    row["Old Circuit ID"] = old_cid
    row["New Circuit ID"] = new_cid

    # =====================================================
    # MAIN CID COLUMN
    # =====================================================
    cid_parts = []

    if new_cid:
        cid_parts.append(f"NEW: {new_cid}")

    if old_cid:
        cid_parts.append(f"OLD: {old_cid}")

    row["CID"] = " | ".join(cid_parts)


def add_request_number(row, ctx):

    result = ctx["result"]

    old_ord = result.get("Old ORD", "")
    new_ord = result.get("New ORD", "")

    row["Old ORD"] = old_ord
    row["New ORD"] = new_ord

    # =====================================================
    # MAIN REQUEST NUMBER COLUMN
    # =====================================================
    ord_parts = []

    if new_ord:
        ord_parts.append(f"NEW: {new_ord}")

    if old_ord:
        ord_parts.append(f"OLD: {old_ord}")

    row["Request Number"] = " | ".join(ord_parts)

def add_current_task(row, ctx):

    tasks = ctx.get("tasks", [])

    # =====================================================
    # FILTER OPEN TASKS
    # =====================================================
    open_tasks = [
        t for t in tasks
        if t.get(
            "statecode@OData.Community.Display.V1.FormattedValue",
            ""
        ) == "Open"
    ]

    # =====================================================
    # NO TASKS
    # =====================================================
    if not open_tasks:
        row["Current Task"] = "No task"
        return

    # =====================================================
    # SORT BY CREATEDON
    # =====================================================
    open_tasks = sorted(
        open_tasks,
        key=lambda x: x.get("createdon") or "",
        reverse=True
    )

    # =====================================================
    # GET SUBJECTS
    # =====================================================
    subjects = []

    for task in open_tasks:

        subject = (task.get("subject") or "").strip()

        if subject and subject not in subjects:
            subjects.append(subject)

    # =====================================================
    # JOIN
    # =====================================================
    row["Current Task"] = " | ".join(subjects)


def add_espt_infra_status(row, ctx):

    result = ctx["result"]

    row["Infra status"] = result.get(
        "Infra status",
        ""
    )

    row["ESPT status"] = result.get(
        "ESPT status",
        ""
    )

def add_nid(row, ctx):
    row["NID"] = ctx["deps"].extract_nid(ctx["resources"]) or "No NID"


def add_latest_so(row, ctx):
    so = ctx["so"]
    row["Latest SO"] = so.get("te_soid") if so else "No SO"




def add_latest_migration_so(row, ctx):
    so = ctx.get("migration_so", {})

    if not so:
        row["Latest Migration by E-Support SO"] = "No SO"
        row["Migration SO Type"] = ""
        row["Migration SO Status"] = ""
        row["Migration Current Task"] = "No Task"
        row["Migration Current Task Owner"] = ""
        return

    row["Latest Migration by E-Support SO"] = so.get("te_soid", "")

    row["Migration SO Type"] = so.get(
        "te_ordertypecode@OData.Community.Display.V1.FormattedValue",
        "",
    )

    row["Migration SO Status"] = so.get(
        "te_serviceorderstatuscode@OData.Community.Display.V1.FormattedValue",
        "",
    )

    # =====================================================
    # CHILD SERVICE ORDERS
    # =====================================================
    child_sos = ctx["deps"].get_child_service_orders(
        ctx["session"],
        so.get("te_serviceorderid", "")
    )

    child_so_ids = [
        x.get("te_serviceorderid")
        for x in child_sos
        if x.get("te_serviceorderid")
    ]

    # =====================================================
    # TASKS
    # =====================================================
    tasks = ctx["deps"].get_tasks(
        ctx["session"],
        so.get("te_serviceorderid", ""),
        child_so_ids
    )

    # Save tasks in context for debug files
    ctx["migration_tasks"] = tasks

    # =====================================================
    # OPEN TASKS ONLY
    # =====================================================
    open_tasks = [
        t for t in tasks
        if (
            t.get("statecode") == 0
            or
            t.get(
                "statecode@OData.Community.Display.V1.FormattedValue",
                ""
            ) == "Open"
        )
    ]

    # =====================================================
    # NO OPEN TASKS
    # =====================================================
    if not open_tasks:
        row["Migration Current Task"] = "No Task"
        row["Migration Current Task Owner"] = ""
        return

    # =====================================================
    # SORT OPEN TASKS
    # =====================================================
    target_tasks = sorted(
        open_tasks,
        key=lambda x: x.get("createdon") or "",
        reverse=True
    )

    # =====================================================
    # SUBJECTS
    # =====================================================
    subjects = []
    owners = []

    for task in target_tasks:
        subject = (task.get("subject") or "").strip()
        owner = task.get("_ownerid_value@OData.Community.Display.V1.FormattedValue", "")

        if subject:
            if subject not in subjects:
                subjects.append(subject)
            if owner and owner not in owners:
                owners.append(owner)

    row["Migration Current Task"] = " | ".join(subjects)
    row["Migration Current Task Owner"] = " | ".join(owners)


def add_so_status(row, ctx):

    so = ctx.get("so", {})

    row["SO Status"] = so.get(
        "te_serviceorderstatuscode@OData.Community.Display.V1.FormattedValue",
        "No Data",
    )

def add_so_type(row, ctx):
    so = ctx["so"]
    row["SO Type"] = (
        so.get("te_ordertypecode@OData.Community.Display.V1.FormattedValue", "No Data")
        if so
        else "No SO"
    )


def add_network_data(row, ctx):
    l3 = ctx["l3"]
    if not l3:
        return

    network_mapping = {
        "VLAN": "VLAN",
        "Interface": "Interface",
        "PE IP": "PE IP",
        "WAN IP": "WAN IP",
        "PE Name": "PE Name",
        "VRF": "VRF",
        "LAN": "LAN",
        "Description": "Description",
        "Config File": "Config File",
    }

    for output_name, source_name in network_mapping.items():
        row[output_name] = l3.get(source_name, "")

def add_work_order_pdf(row, ctx):
    deps = ctx["deps"]
    wo_issue_date = ""

    try:
        session = ctx["session"]
        order = ctx["order"]
        resources = ctx.get("resources") or deps.get_resources(session, order)
        ctx["resources"] = resources

        pdf_path = ""
        if resources:
            # تحديد المعرف الأنسب ليكون هو "رقم أمر الشغل" (Work Order ID)
            wo_id = None

            # 1. إذا كان الإدخال الأصلي CID، نستخدمه مباشرة
            if ctx.get("input_cid"):
                wo_id = ctx["input_cid"]
            
            # 2. الأولوية للدائرة الجديدة (New Circuit ID) المستخرجة من منطق الـ ORD
            if not wo_id and ctx.get("result"):
                wo_id = ctx["result"].get("New Circuit ID")

            # 3. إذا لم يوجد جديد، نستخدم الدائرة القديمة (Old Circuit ID) كخيار ثانٍ
            if not wo_id and ctx.get("result"):
                wo_id = ctx["result"].get("Old Circuit ID")

            # 4. خيار احتياطي: البحث عن أحدث دائرة نشطة عامة
            if not wo_id:
                for r in resources:
                    state_code = r.get("statecode@OData.Community.Display.V1.FormattedValue")
                    resource_family = r.get("te_resourceramilycode@OData.Community.Display.V1.FormattedValue")
                    cid_val = r.get("te_circuitid")
                    if state_code == "Active" and resource_family == "Transmission Media" and cid_val:
                        wo_id = str(cid_val).strip()
                        break

            # Fallback: If no specific CID found, use the resolved ECRM order number
            if not wo_id:
                wo_id = order
            
            # Ensure wo_id is a string
            wo_id = str(wo_id).strip()

            # Receive returned values: (PDF Path, Issue Date)
            pdf_path, wo_issue_date = find_work_order_pdf(
                deps,
                session,
                wo_id,
                resources,
                ctx["result"],
                debug=ctx.get("debug_mode", False),
            )

        row["Work Order PDF"] = pdf_path or "No PDF Found"
        row["WO issue Date"] = wo_issue_date

        # --- التكامل مع WO Extractor ---
        if pdf_path and os.path.exists(pdf_path):
            # التأكد من وجود Transmission Type أولاً لتحديد نمط الاستخراج
            transmission_val = row.get("Transmission Type")
            if not transmission_val:
                add_transmission_media(row, ctx)
                transmission_val = row.get("Transmission Type")
            
            # استخدام النوع المكتشف أو الافتراض بـ GPON
            mode = str(transmission_val or "GPON")
            
            # محاولة الربط مع المحرك الموحد
            mode_upper = mode.upper()
            # التأكد من أن النمط مدعوم (GPON, Fiber, Local Loop, WiMax)
            supported_modes = ["GPON", "FIBER", "LOCAL LOOP", "WIMAX"]
            
            if any(m in mode_upper for m in supported_modes):
                try:
                    # تحديد مسار أداة WO Unified
                    base_path = Path(__file__).resolve().parent.parent.parent
                    wo_runner_path = base_path / "WO Unified" / "wo_unified_runner.py"
                    
                    if wo_runner_path.exists():
                        spec = importlib.util.spec_from_file_location("wo_runner", str(wo_runner_path))
                        wo_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(wo_module)
                        
                        # استدعاء المحرك الموحد الجديد
                        if hasattr(wo_module, "extract_from_pdf_to_dict"):
                            extracted_data = wo_module.extract_from_pdf_to_dict(pdf_path, mode_upper)
                            if extracted_data:
                                row.update(extracted_data)
                except Exception as e:
                    if ctx.get("debug_mode"):
                        print(f"DEBUG: WO Extractor integration failed: {e}")

    except Exception as exc:
        row["Work Order PDF"] = f"Error: {exc}"
        row["WO issue Date"] = wo_issue_date


        
def add_customer_name_arabic(row, ctx):
    row["CST Name Arabic"] = ctx["customer_json"].get("te_name_ar", "")


def add_customer_type(row, ctx):
    row["CST Type"] = ctx["customer_json"].get(
        "_te_customertypeid_value@OData.Community.Display.V1.FormattedValue",
        "",
    )


def add_customer_category(row, ctx):
    row["CST Category"] = ctx["customer_json"].get(
        "_te_customercategoryid_value@OData.Community.Display.V1.FormattedValue",
        "",
    )

def add_account_manager(row, ctx):
    row["Account manager"] = ctx["customer_json"].get(
        "_te_accountmanagersystemuserid_value@OData.Community.Display.V1.FormattedValue",
        "",
    )


def add_account_manager_mail(row, ctx):
    row["Account manager mail"] = ctx["user_json"].get("internalemailaddress", "")


def add_branch_address(row, ctx):
    if ctx["branch_data"]:
        row["Branch Address"] = ctx["branch_data"].get("te_street1_ar", "")


def add_customer_number(row, ctx):
    if ctx["branch_data"]:
        row["CST Number"] = ctx["branch_data"].get("accountnumber", "")


def add_msan_data(row, ctx):
    deps = ctx["deps"]
    session = ctx["session"]

    row["MSAN Code"] = ""
    row["MSAN IP"] = ""
    row["MSAN Name"] = ""
    row["Shelf"] = ""
    row["Card"] = ""
    row["Port"] = ""
    row["Comment"] = ""
    row["Description"] = ""
    row["RR Port"] = ""

    # ابحث فقط عن Transmission Media
    transmission_media = next(
        (
            r for r in ctx["resources"]
            if r.get(
                "te_resourceramilycode@OData.Community.Display.V1.FormattedValue"
            ) == "Transmission Media"
        ),
        None,
    )

    if not transmission_media:
        return

    # Port المختار فعلياً فى الـ Lookup
    port_id = transmission_media.get("_te_portsid_value")

    # لو مفيش Port مختار خلي RR Port فاضي
    if not port_id:
        return

    port = deps.get_port_full_data(session, port_id) or {}

    row["MSAN Code"] = (
        port.get("ted_msancodeinfo")
        or port.get("_te_msancodeid_value@OData.Community.Display.V1.FormattedValue", "")
    )

    row["MSAN IP"] = port.get("ted_dslammsanip", "")
    row["MSAN Name"] = port.get("te_dslammsanname") or port.get("te_productpopnamehidden") or ""
    row["Shelf"] = port.get("te_shelfno") or ""
    row["Card"] = port.get("te_cardno") or ""
    row["Port"] = port.get("te_portno") or ""
    row["Comment"] = port.get("te_commentml") or ""
    row["Description"] = port.get("te_description") or ""

    # RR Port يظهر فقط لو الـ Lookup مختار فعلاً
    row["RR Port"] = port.get("te_name") or ""

    
def add_installed_resources(row, ctx):
    """Extract all Resources linked to Active Installed Base Lines"""
    installed = ctx.get("installed", [])
    resources = ctx.get("resources", [])
    
    # 1) Collect Active IB Line IDs
    active_ib_ids = {
        item.get("contractdetailid")
        for item in installed
        if item.get("statuscode@OData.Community.Display.V1.FormattedValue") == "Active"
    }

    if not active_ib_ids:
        row["Installed Resources"] = "No Active IB Found"
        return

    # 2) Find Resources linked to these IDs
    linked_names = [
        res.get("te_name") or res.get("te_resourceidentifier")
        for res in resources
        if res.get("_ted_te_installedbaselines_value") in active_ib_ids
    ]

    row["Installed Resources"] = " | ".join(filter(None, linked_names)) if linked_names else "No Linked Resources"


def add_notes(row, ctx):
    deps = ctx["deps"]
    session = ctx["session"]
    so = ctx.get("so")
    migration_so = ctx.get("migration_so")

    notes_list = []

    # Check for notes in Main SO and Migration SO
    targets = [(so, "Main"), (migration_so, "Migration")]

    # Check specific orders
    for target_so, label in targets:
        if not target_so:
            continue
            
        so_id = target_so.get("te_serviceorderid")
        notes = deps.get_notes(session, so_id) if so_id else []

        if notes:
            # Select latest note based on modification or creation date
            latest_note = max(
                notes, 
                key=lambda x: x.get("modifiedon") or x.get("createdon") or ""
            )
            text = (latest_note.get("notetext") or "").strip()
            if text:
                notes_list.append(f"[{label}] {text}")

    row["Notes"] = " | ".join(notes_list)

def add_order_field(row, ctx):
    row["Order"] = ctx.get("order", "")

def add_onu_tech_data(row, ctx):
    installed = ctx.get("installed", [])
    is_gpon = False
    for item in installed:
        product = item.get(
            "_productid_value@OData.Community.Display.V1.FormattedValue",
            ""
        )
        if "GPON" in str(product).upper():
            is_gpon = True
            break

    if not is_gpon:
        row["ONU Tech Data"] = "Not GPON"
        return

    result = ctx.get("result", {})
    
    # استخراج الـ ORDs ووضعها في الـ row لتظهر في الإكسيل تلقائياً
    old_ord_val = result.get("Old ORD", "")
    new_ord_val = result.get("New ORD", "")
    row["Old ORD"] = old_ord_val
    row["New ORD"] = new_ord_val

    new_ord = new_ord_val

    if not new_ord:

        potential_ord = str(
            ctx.get("order", "")
        )

        if "ORD-" in potential_ord.upper():
            new_ord = potential_ord

    if not new_ord:

        resources = ctx.get(
            "resources",
            []
        )

        for res in resources:

            val = res.get(
                "new_orderlinenumberid"
            )

            if val:
                new_ord = val
                row["New ORD"] = val # تحديث القيمة في الإكسيل لو وجدت في الـ resources
                break

    if not new_ord:
        row["ONU Tech Data"] = "New ORD not found"
        return

    try:

        tech_data = ctx["deps"].fetch_ftth_portal_data(
            new_ord,
            ctx.get("gui")
        )

        if not tech_data:
            row["ONU Tech Data"] = "No Data"
            return

        if isinstance(tech_data, dict):
            # Flexible map to match portal fields with column headers
            MAPPING = {
                "kam order no": "Order Number",
                "kam order": "Order Number",
                "order number": "Order Number",
                "kam_order": "Order Number",
                "governorate": "Governorate",
                "area": "Area",
                "splitter name": "Splitter",
                "splitter": "Splitter",
                "olt name": "OLT Name",
                "olt": "OLT Name",
                "shelf no": "Shelf",
                "shelf": "Shelf",
                "slot no": "ONT ID",
                "slot": "ONT ID",
                "port no": "Port",
                "port": "Port",
                "msanport": "Port",
                "msanip": "MSAN IP",
                "msancode": "MSAN Code",
                "tedmsanip": "MSAN IP",
                "onu serial number": "ONU Serial Number",
                "onu sn": "ONU Serial Number",
                "serial no": "ONU Serial Number",
                "onu serial no": "ONU Serial Number",
                "ontserialno": "ONU Serial Number",
                "ont serial number": "ONU Serial Number",
                "serial number": "ONU Serial Number",
                "onu serial": "ONU Serial Number",
                "vendorname": "Cabinet vendor",
                "ispname": "ISPName",
                "onu status": "ONU Status",
                "wostatus": "ONU Status",
                "ontstatus": "ONU Status",
                "rx power(dbm)": "RX Power",
                "tx power(dbm)": "TX Power",
                "rx power": "RX Power",
                "tx power": "TX Power",
                "line profile": "Line Profile",
                "service profile": "Service Profile",
                "dataservice": "Service Profile",
                "ontchannel": "ONT ID",
                "acceptancedate": "Acceptance Date",
                "downspeed": "Down Speed",
                "upspeed": "Up Speed"
            }

            found_any = False
            for key, value in tech_data.items():
                # تنظيف المفتاح بشكل احترافي لإزالة المسافات المخفية والرموز
                key_str = str(key).split(':')[0]
                # إزالة \xa0 (non-breaking space) وأي مسافات زائدة
                clean_key = " ".join(key_str.split()).lower()
                
                # Map key, fallback to Title case if not found
                target_key = MAPPING.get(clean_key)
                if not target_key:
                    target_key = clean_key.title()

                row[target_key] = value
                found_any = True
                
            # بعد انتهاء الحلقة، نتحقق من وجود السيريال نمبر لتوليد الـ Vendor
            serial_val = row.get("ONU Serial Number")
            if serial_val:
                from ecrm_extractor.domain.extractors import get_onu_vendor
                vendor_name = get_onu_vendor(serial_val)
                row["ONU Vendor"] = vendor_name

            if found_any:
                row["ONU Tech Data"] = "Fetched Successfully"

        else:

            row["ONU Tech Data"] = str(
                tech_data
            )

    except Exception as e:

        row["ONU Tech Data"] = (
            f"Portal Error: {str(e)}"
        )

FIELD_HANDLERS = {
    "CST Name": add_customer_name,
    "Branch": add_branch,
    "POP": add_pop,
    "Speed": add_speed,
    "Order Status": add_order_status,
    "Circuit Status": add_circuit_status,
    "CID": add_cid,
    "Request Number": add_request_number,
    "Current Task": add_current_task,
    "ESPT & infra status": add_espt_infra_status,
    "NID": add_nid,
    "Latest SO": add_latest_so,
    "Latest Migration by E-Support SO": add_latest_migration_so,
    "SO Status": add_so_status,
    "SO Type": add_so_type,
    "Migration SO Type": add_latest_migration_so,
    "Migration SO Status": add_latest_migration_so,
    "Migration Current Task": add_latest_migration_so,
    "Migration Current Task Owner": add_latest_migration_so,
    "Work Order PDF": add_work_order_pdf,
    "Network Data": add_network_data,
    "CST Name Arabic": add_customer_name_arabic,
    "CST Type": add_customer_type,
    "CST Category": add_customer_category,
    "Account manager": add_account_manager,
    "Account manager mail": add_account_manager_mail,
    "Branch Address": add_branch_address,
    "CST Number": add_customer_number,
    "MSAN Data": add_msan_data,
    "Product": add_product,
    "Transmission Type": add_transmission_media,
    "Hardware": add_product,
    "Installed Resources": add_installed_resources,
    "Order": add_order_field,
    "Notes": add_notes,
    "ONU Tech Data": add_onu_tech_data,
}


def apply_selected_fields(row, ctx, selected):
    if (
        "Hardware" in selected
        and "Product" not in selected
    ):
        add_product(row, ctx)

    for field_name, handler in FIELD_HANDLERS.items():

        if field_name == "Hardware":
            continue

        if field_name in selected:
            handler(row, ctx)

    # =====================================================
    # AUTOMATION: Trigger PDF if ESPT status is Work Order
    # =====================================================
    # Case-insensitive status check

    espt_raw = row.get("ESPT status") or ""
    espt_status = str(espt_raw).strip().lower()
    
    is_espt_infra_selected = "ESPT & infra status" in selected
    is_espt_work_order = (espt_status == "work order")
    is_wo_pdf_not_selected = "Work Order PDF" not in selected
    
    # تم إيقاف منطق الأتمتة التلقائية بناءً على طلب المستخدم لإلغاء Quick Actions
    if ctx.get("debug_mode", False):
        print(f"DEBUG (Order {ctx.get('order')}): Automation check - ESPT Status: {espt_status}")
