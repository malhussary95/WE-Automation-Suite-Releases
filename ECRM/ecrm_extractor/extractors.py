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



def extract_order_status_from_ib(installed):
    """
    Order Status from Installed Base Line.

    Priority:
    1. Active Service IB -> Active
    2. If no Active Service -> latest Service status
    """

    service_rows = []

    for row in installed or []:

        # Service only
        if row.get("te_producttypecode") != 1:
            continue

        service_rows.append(row)

    if not service_rows:
        return ""

    # =====================================================
    # ACTIVE SERVICE = CURRENT ORDER STATUS
    # =====================================================

    active_services = [
        row
        for row in service_rows
        if (
            row.get("statecode") == 0
            and row.get("statuscode") == 1
        )
    ]

    if active_services:

        # If multiple active services,
        # use the latest created one.
        latest_active = max(
            active_services,
            key=lambda x: x.get("createdon") or ""
        )

        return (
            latest_active.get(
                "statuscode@OData.Community.Display.V1.FormattedValue"
            )
            or "Active"
        )

    # =====================================================
    # NO ACTIVE SERVICE
    # =====================================================

    latest_service = max(
        service_rows,
        key=lambda x: x.get("createdon") or ""
    )

    return (
        latest_service.get(
            "statuscode@OData.Community.Display.V1.FormattedValue"
        )
        or latest_service.get("statuscode")
        or ""
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
    """Strict NEW/OLD extraction for resource rows.

    NEW = Keep + Transmission Media.
    OLD = Terminate + Transmission Media.
    Values are read from the matching row only; no fallback is allowed.
    """
    result = {
        "Old Circuit ID": "",
        "New Circuit ID": "",
        "Old ORD": "",
        "New ORD": "",
        "Infra status": "",
        "ESPT status": "",
    }

    def clean(value):
        if value is None:
            return ""
        return str(value).strip()

    new_found = False
    old_found = False

    for r in resources or []:
        family = clean(
            r.get(
                "rr_x002e_te_resourceramilycode@OData.Community.Display.V1.FormattedValue"
            )
        )
        action = clean(
            r.get(
                "te_changeactioncode@OData.Community.Display.V1.FormattedValue"
            )
        )

        if family != "Transmission Media":
            continue

        if action == "Keep" and not new_found:
            new_found = True
            result["New Circuit ID"] = clean(r.get("rr_x002e_te_circuitid"))
            result["New ORD"] = clean(r.get("rr_x002e_te_requestnumber"))
            result["Infra status"] = clean(
                r.get(
                    "rr_x002e_te_infrastructureavailabilitystatusnewcode@OData.Community.Display.V1.FormattedValue"
                )
            )
            result["ESPT status"] = clean(
                r.get(
                    "rr_x002e_te_esptstatuscode@OData.Community.Display.V1.FormattedValue"
                )
            )

        elif action == "Terminate" and not old_found:
            old_found = True
            result["Old Circuit ID"] = clean(r.get("rr_x002e_te_circuitid"))
            result["Old ORD"] = clean(r.get("rr_x002e_te_requestnumber"))

        if new_found and old_found:
            break

    return result

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
