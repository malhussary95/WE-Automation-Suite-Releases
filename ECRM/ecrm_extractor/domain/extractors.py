def get_text(row, field):
    return row.get(
        field + "@OData.Community.Display.V1.FormattedValue",
        row.get(field, "")
    )


def get_latest_commercial_so(service_orders):

    candidates = [
        so for so in service_orders
        if (

            # =================================================
            # COMMERCIAL ORDER PRODUCT
            # =================================================
            so.get(
                "te_serviceordertypecode@OData.Community.Display.V1.FormattedValue",
                ""
            ) == "Commercial Order Product"

            and

            # =================================================
            # DATA SERVICES ONLY
            # =================================================
            so.get(
                "te_productfamilycode@OData.Community.Display.V1.FormattedValue",
                ""
            ) == "Data Services"
        )
    ]

    if not candidates:
        return {}

    # 🔥 الأحدث
    return max(
        candidates,
        key=lambda x: x.get("createdon") or ""
    )

def get_pdf_from_notes(notes):
    pdfs = []

    for n in notes:
        name = (n.get("filename") or "").lower()
        mimetype = (n.get("mimetype") or "").lower()

        if name.endswith(".pdf") or mimetype == "application/pdf":
            pdfs.append(n)

    return pdfs[0] if pdfs else None


def get_pdfs_from_notes(notes):
    pdfs = []

    for n in notes or []:
        name = (n.get("filename") or "").lower()
        mimetype = (n.get("mimetype") or "").lower()

        if name.endswith(".pdf") or mimetype == "application/pdf":
            pdfs.append(n)

    return pdfs


def enrich_installed_with_speed(installed, product_flats):

    enriched = []

    for row in installed:

        pf = product_flats.get(row.get("_te_productflatid_value"), {})

        # ✅ خد السرعة فقط من product_flat
        speed = pf.get("te_speed")

        new_row = dict(row)
        new_row["_product_flat"] = pf
        new_row["_speed"] = speed

        enriched.append(new_row)

    return enriched


def extract_speed(installed):

    # فلترة السجلات للحصول على الخدمات النشطة فقط وتجنب السجلات الملغاة أو المنتهية
    active_services = [
        item for item in installed
        if (
            item.get("_product_flat", {}).get("te_producttype") == "Service"
            and (item.get("statuscode") == 1 or item.get("statuscode@OData.Community.Display.V1.FormattedValue") == "Active")
        )
    ]

    if not active_services:
        return ""

    # اختيار السجل الأحدث بناءً على تاريخ الإنشاء لضمان دقة البيانات
    latest_active = max(
        active_services,
        key=lambda x: x.get("createdon") or ""
    )

    return latest_active.get("_speed") or ""


def extract_order_status_from_commercial(commercial_orders, order):
    """
    Determine Order Status from Commercial Orders.

    Rules:
    - Order not found -> not found
    - Only Service records are considered.
    - Sort Service records newest -> oldest.
    - Fulfilled -> Active
    - InFlight / Canceled -> skip and check previous Service
    - Sales Termination -> Terminated
    - Any other status -> Active
    """

    order = str(order or "").strip()

    if not order:
        return "not found"

    # =====================================================
    # 1) FILTER ORDER
    # =====================================================

    order_rows = [
        row for row in (commercial_orders or [])
        if str(
            row.get("te_orderlinenumber")
            or row.get("te_orderlinenumberid")
            or ""
        ).strip() == order
    ]

    if not order_rows:
        return "not found"

    # =====================================================
    # 2) SERVICE ONLY
    # =====================================================

    service_rows = [
        row for row in order_rows
        if (
            str(
                row.get(
                    "te_producttype@OData.Community.Display.V1.FormattedValue"
                )
                or row.get(
                    "te_producttypecode@OData.Community.Display.V1.FormattedValue"
                )
                or ""
            ).strip().lower()
            == "service"
        )
    ]

    if not service_rows:
        return "not found"

    # =====================================================
    # 3) NEWEST FIRST
    # =====================================================

    service_rows.sort(
        key=lambda x: (
            x.get("createdon")
            or x.get("modifiedon")
            or ""
        ),
        reverse=True
    )

    # =====================================================
    # 4) CHECK FROM NEWEST TO OLDEST
    # =====================================================

    for row in service_rows:

        status = str(
            row.get(
                "te_statuscode@OData.Community.Display.V1.FormattedValue"
            )
            or row.get(
                "statuscode@OData.Community.Display.V1.FormattedValue"
            )
            or ""
        ).strip().lower()

        order_type = str(
            row.get(
                "te_ordertypecode@OData.Community.Display.V1.FormattedValue"
            )
            or ""
        ).strip().lower()

        service_order_type = str(
            row.get(
                "te_serviceordertypecode@OData.Community.Display.V1.FormattedValue"
            )
            or ""
        ).strip().lower()

        # =================================================
        # SALES TERMINATION
        # =================================================

        if (
            "sales termination" in order_type
            or "sales termination" in service_order_type
        ):
            return "Terminated"

        # =================================================
        # SKIP THESE AND CHECK PREVIOUS
        # =================================================

        if status in {
            "in flight",
            "inflight",
            "canceled",
            "cancelled",
        }:
            continue

        # =================================================
        # FULFILLED
        # =================================================

        if status == "fulfilled":
            return "Active"

        # =================================================
        # ANY OTHER STATUS
        # =================================================

        return "Active"

    # =====================================================
    # NO VALID SERVICE RECORD
    # =====================================================

    return "not found"


def extract_order_status_from_ib(installed):
    service_rows = [
        row for row in installed
        if row.get("te_producttypecode") == 1
    ]

    if not service_rows:
        return ""

    # IMPORTANT:
    # The Installed Base Line status is determined by the
    # latest modification, NOT the creation date.
    latest = max(
        service_rows,
        key=lambda x: x.get("modifiedon") or ""
    )

    return latest.get(
        "statuscode@OData.Community.Display.V1.FormattedValue",
        ""
    )

def extract_old_new_from_so(rows, so, order=None, debug=False):
    """
    Extract NEW/OLD Transmission Media values strictly from the matching row.

    NEW requires:
      - te_changeactioncode FormattedValue == Keep
      - rr_x002e_te_resourceramilycode FormattedValue == Transmission Media

    OLD requires:
      - te_changeactioncode FormattedValue == Terminate
      - rr_x002e_te_resourceramilycode FormattedValue == Transmission Media

    IMPORTANT: There is NO fallback between NEW and OLD rows and no statecode
    based classification. Missing keys / null values remain empty.
    """
    from ecrm_extractor.core.storage import save_json

    result = {
        "Old Circuit ID": "",
        "New Circuit ID": "",
        "Old ORD": "",
        "New ORD": "",
        "Infra status": "",
        "ESPT status": "",
        "New Resource ID": "",
        "Old Resource ID": "",
    }

    new_source_row = None
    old_source_row = None

    def rr_value(row, field):
        """Read only the requested RR/OData alias, without falling back to raw te_* values."""
        return row.get(f"rr_x002e_{field}")

    def rr_formatted(row, field):
        return row.get(
            f"rr_x002e_{field}@OData.Community.Display.V1.FormattedValue"
        )

    def clean(value):
        if value is None:
            return ""
        return str(value).strip()

    for row in rows or []:
        action = clean(
            row.get(
                "te_changeactioncode@OData.Community.Display.V1.FormattedValue"
            )
        )
        family = clean(
            row.get(
                "rr_x002e_te_resourceramilycode@OData.Community.Display.V1.FormattedValue"
            )
        )

        # The family condition is EXACTLY Transmission Media.
        if family != "Transmission Media":
            continue

        # =================================================
        # NEW: Keep + Transmission Media ONLY
        # =================================================
        if action == "Keep" and new_source_row is None:
            new_source_row = row

            # Read ONLY from this NEW row.
            result["New Circuit ID"] = clean(rr_value(row, "te_circuitid"))
            result["New ORD"] = clean(rr_value(row, "te_requestnumber"))
            result["Infra status"] = clean(
                rr_formatted(
                    row, "te_infrastructureavailabilitystatusnewcode"
                )
            )
            result["ESPT status"] = clean(
                rr_formatted(row, "te_esptstatuscode")
            )

        # =================================================
        # OLD: Terminate + Transmission Media ONLY
        # =================================================
        if action == "Terminate" and old_source_row is None:
            old_source_row = row

            # Read ONLY from this OLD row.
            result["Old Circuit ID"] = clean(rr_value(row, "te_circuitid"))
            result["Old ORD"] = clean(rr_value(row, "te_requestnumber"))

        if new_source_row is not None and old_source_row is not None:
            break

    if debug and order:
        save_json(
            order,
            "RESULT_SOURCE_RESOURCES",
            {
                "new_row_data": new_source_row,
                "old_row_data": old_source_row,
                "all_transmission_media_rows": rows,
            },
        )

    return result

def extract_hardware_from_service_order(installed, so, product_flats):

    ib_id = so.get("_te_installedbaselineid_value")

    result = []

    for row in installed:

        if row.get("contractdetailid") != ib_id:
            continue

        pf = product_flats.get(row.get("_te_productflatid_value"), {})

        if pf.get("te_producttype") == "Hardware":
            result.append(pf.get("te_productname"))

    return " - ".join(result)


def filter_by_so(data, so):
    so_id = so.get("te_serviceorderid")

    return [
        x for x in data
        if x.get("_te_serviceorderid_value") == so_id
    ]


def get_latest_data_services_so(service_orders):

    # فلترة Data Services
    data_sos = [
        so for so in service_orders
        if so.get(
            "te_productfamilycode@OData.Community.Display.V1.FormattedValue"
        ) == "Data Services"
    ]

    if not data_sos:
        return {}

    # هات أحدث واحد
    return max(
        data_sos,
        key=lambda x: x.get("modifiedon", "")
    )


def get_latest_migration_esupport_so(service_orders):

    candidates = [
        so for so in service_orders
        if (

            # =================================================
            # DATA SERVICES ONLY
            # =================================================
            so.get(
                "te_productfamilycode@OData.Community.Display.V1.FormattedValue",
                ""
            ) == "Data Services"

            and

            # =================================================
            # MIGRATION BY E-SUPPORT
            # =================================================
            so.get(
                "te_ordertypecode@OData.Community.Display.V1.FormattedValue",
                ""
            ) == "Migration by E-Support"

            and

            # =================================================
            # COMMERCIAL ORDER PRODUCT
            # =================================================
            so.get(
                "te_serviceordertypecode@OData.Community.Display.V1.FormattedValue",
                ""
            ) == "Commercial Order Product"
        )
    ]

    if not candidates:
        return {}

    return max(
        candidates,
        key=lambda x: x.get("createdon") or ""
    )



def extract_full_data(resources):

    old_circuits = []
    new_circuits = []

    old_reqs = []
    new_reqs = []

    seen_old_cid = set()
    seen_new_cid = set()

    seen_old_req = set()
    seen_new_req = set()

    infra_status = ""
    espt_status = ""

    for r in resources:

        # =================================================
        # ONLY Transmission Media
        # =================================================
        family = str(r.get("te_resourceramilycode@OData.Community.Display.V1.FormattedValue", "")).strip()
        if "Transmission Media" not in family:
            continue

        cid = str(r.get("te_circuitid") or "").strip()
        req = str(r.get("te_requestnumber") or "").strip()

        action = str(r.get("te_changeactioncode@OData.Community.Display.V1.FormattedValue", "")).strip().lower()
        state = r.get("statecode")

        # =================================================
        # NEW = ACTIVE / KEEP / MODIFY
        # =================================================
        is_new = any(x in action for x in ["keep", "modify", "provide", "add", "new"]) or state == 0
        if is_new:

            if cid and cid not in seen_new_cid:
                seen_new_cid.add(cid)
                new_circuits.append(cid)

            if req and req not in seen_new_req:
                seen_new_req.add(req)
                new_reqs.append(req)

            # statuses from NEW only
            if not infra_status:
                infra_status = r.get(
                    "te_infrastructureavailabilitystatusnewcode@OData.Community.Display.V1.FormattedValue",
                    ""
                )

            if not espt_status:
                espt_status = r.get(
                    "te_esptstatuscode@OData.Community.Display.V1.FormattedValue",
                    ""
                )

        # =================================================
        # OLD = INACTIVE / TERMINATE
        # =================================================
        is_old = any(x in action for x in ["terminate", "cease", "remove", "old"]) or state == 1
        if is_old:

            if cid and cid not in seen_old_cid:
                seen_old_cid.add(cid)
                old_circuits.append(cid)

            if req and req not in seen_old_req:
                seen_old_req.add(req)
                old_reqs.append(req)

    return {
        "Old Circuit ID": " - ".join(old_circuits),
        "New Circuit ID": " - ".join(new_circuits),

        "Old ORD": " - ".join(old_reqs),
        "New ORD": " - ".join(new_reqs),

        "Infra status": infra_status,
        "ESPT status": espt_status
    }

def extract_l3_data(resources, order=None, debug=False):

    from ecrm_extractor.core.storage import save_json

    matches = []

    for r in resources:

        comp = r.get(
            "te_resourcecomponentcode@OData.Community.Display.V1.FormattedValue",
            ""
        )

        # جعل التحقق أكثر مرونة ليشمل أنواع مختلفة من الـ L3
        if any(x in comp for x in [
            "PE - L3 Basic", 
            "PE - L3", 
            "Service configuration | PE"
        ]):

            item = {
                "resource_id": r.get("te_resourceregistryid"),
                "component": comp,

                "VLAN": r.get("te_vlan") or r.get("te_vlanservicedatabasic"),
                "Interface": r.get("te_interfacedescription"),
                "PE IP": r.get("te_peipaddress"),
                "WAN IP": r.get("te_wanip"),
                "PE Name": r.get("te_pehostname"),
                "VRF": r.get("te_vrfnameservicedatabasic"),
                "LAN": r.get("te_lanip"),
                "Description": r.get("te_interfacedescription"),
                "Config File": r.get("ted_configfile", ""),

                # FULL RAW RESOURCE
                "raw_resource": r
            }

            matches.append(item)

    # =========================================
    # SAVE FULL DEBUG JSON
    # =========================================
    if debug and order:
        save_json(
            order,
            "L3_FULL_DEBUG",
            matches
        )

    # =========================================
    # RETURN FIRST MATCH FOR NORMAL FLOW
    # =========================================
    if matches:
        first = matches[0].copy()
        first.pop("raw_resource", None)
        return first

    return {}


def extract_msan_data(resources):
    for r in resources:
        comp = r.get(
            "te_resourcecomponentcode@OData.Community.Display.V1.FormattedValue",
            ""
        )

        # البحث عن المكونات الخاصة بالـ Access أو MSAN
        if any(x in comp for x in ["MSAN", "DSLAM", "Access Configuration", "GPON"]):
            return {
                "MSAN Code": r.get("ted_msancodeinfo") or "",
                "MSAN IP": r.get("ted_dslammsanip") or "",
                "Shelf": r.get("te_shelf") or r.get("te_shelfno") or "",
                "Slot": r.get("te_slot"),
                "Port": r.get("te_port") or r.get("te_portno") or "",
                "Card": r.get("te_cardname") or r.get("te_cardno") or "",
                "Subslot": r.get("te_subslot"),
                "OLT": r.get("te_oltname") or r.get("te_pehostname"),
            }

    return {}


def extract_nid(resources):

    for r in resources:

        nid = r.get("te_nid")

        if nid:
            return nid

    return ""


def extract_circuits(resources):
    old_circuits = []
    new_circuits = []
    seen_old = set()
    seen_new = set()

    for r in resources:
        cid = r.get("te_circuitid")
        action = str(r.get("te_changeactioncode@OData.Community.Display.V1.FormattedValue", "")).strip().lower()
        state = r.get("statecode")

        if not cid:
            continue

        cid = str(cid).strip()

        # =========================
        # LOGIC الحقيقي
        # =========================
        if action in ["keep", "modify"] or state == 0:  # Active / Keep / Modify
            if cid not in seen_new:
                seen_new.add(cid)
                new_circuits.append(cid)

        elif action == "terminate" or state == 1:  # Inactive / Terminate
            if cid not in seen_old:
                seen_old.add(cid)
                old_circuits.append(cid)

    return {
        "Old Circuit ID": " - ".join(old_circuits),
        "New Circuit ID": " - ".join(new_circuits)
    }


def extract_hardware(installed):
    hw = []

    for row in installed:
        txt = str(row).lower()

        if "hardware" in txt or "router" in txt or "cpe" in txt:
            hw.append({
                "HW Name": row.get("title", ""),
                "HW Product": get_text(row, "_productid_value"),
                "HW Status": get_text(row, "statuscode"),
                "HW State": get_text(row, "statecode"),
                "Product": row.get("te_service", ""),   # NEW
            })

    return hw


def get_onu_vendor(serial_hex):
    """
    يحدد مصنع جهاز الـ ONU عن طريق فك تشفير أول 8 رموز Hex في الرقم التسلسلي.
    """
    try:
        serial_str = str(serial_hex).strip()
        if not serial_str or len(serial_str) < 8:
            return ""

        # أول 4 بايت (8 رموز hex) تمثل Vendor ID بنظام ASCII
        vendor_id = bytes.fromhex(serial_str[:8]).decode("ascii")
        vendors = {
            "HWTC": "Huawei",
            "ZTEG": "ZTE",
            "ALCL": "Nokia / Alcatel-Lucent",
            "NOKG": "Nokia",
            "FHTT": "FiberHome",
            "TPLG": "TP-Link",
        }
        return vendors.get(vendor_id, f"Unknown ({vendor_id})")
    except:
        return "Invalid Serial"
