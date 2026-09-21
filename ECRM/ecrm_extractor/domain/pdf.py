import os


def is_document_activity(activity):
    return (
        activity.get("@odata.type") == "#Microsoft.Dynamics.CRM.te_document"
        or activity.get("activitytypecode") == "te_document"
        or (
            activity.get("activitytypecode@OData.Community.Display.V1.FormattedValue")
            == "Document"
        )
        or (activity.get("subject") or "").strip().upper().startswith("DOC")
    )


def ordered_document_activities(activities):
    docs = [
        activity for activity in activities
        if is_document_activity(activity)
    ]
    docs = sorted(
        docs,
        key=lambda activity: activity.get("modifiedon") or activity.get("createdon") or "",
        reverse=True,
    )
    doc_subjects = [
        activity for activity in docs
        if (activity.get("subject") or "").strip().upper().startswith("DOC")
    ]
    other_docs = [activity for activity in docs if activity not in doc_subjects]
    return doc_subjects + other_docs


def resource_ids_for_pdf(resources, result):
    """
    Get resource IDs ordered by newest circuit ID first.
    Returns: tuple (ordered_ids_list, wo_issue_date)
    """
    raw_cid = str(result.get("New Circuit ID", "")).strip()
    new_cid = raw_cid.split("-")[0].strip() if raw_cid else ""

    resources_with_cid = []
    fallback = []

    for resource in resources:
        rr_id = resource.get("te_resourceregistryid")
        if not rr_id:
            continue

        cid_val = str(resource.get("te_circuitid", "")).strip()
        created_on = resource.get("createdon") or ""
        modified_on = resource.get("modifiedon") or ""
        modified_on_formatted = resource.get("modifiedon@OData.Community.Display.V1.FormattedValue", "")
        
        action = resource.get(
            "te_changeactioncode@OData.Community.Display.V1.FormattedValue",
            "",
        ).lower()

        # Skip cancelled resources
        status = resource.get(
            "te_esptstatuscode@OData.Community.Display.V1.FormattedValue", ""
        ).lower()
        if "cancelled" in status:
            continue

        # Skip invalid circuit IDs
        if cid_val in ("", "000", "None"):
            if "keep" in action or "modify" in action:
                fallback.append(rr_id)
            continue

        resources_with_cid.append({
            "rr_id": rr_id,
            "cid": cid_val,
            "created_on": created_on,
            "modified_on": modified_on,
            "modified_on_formatted": modified_on_formatted,
            "matches_new_cid": (cid_val == new_cid) if new_cid else False,
        })

    # Sort by date (newest first)
    resources_with_cid.sort(
        key=lambda x: x["modified_on"] or x["created_on"],
        reverse=True,
    )

    # Build ordered list
    ordered = []

    for r in resources_with_cid:
        if r["matches_new_cid"] and r["rr_id"] not in ordered:
            ordered.append(r["rr_id"])

    for r in resources_with_cid:
        if not r["matches_new_cid"] and r["rr_id"] not in ordered:
            ordered.append(r["rr_id"])

    for rr_id in fallback:
        if rr_id not in ordered:
            ordered.append(rr_id)

    # استخراج WO Issue Date من أحدث Resource تم اختياره
    wo_issue_date = ""
    if resources_with_cid:
        # ناخد التاريخ من الـ Resource المتطابق مع New CID الأول
        for r in resources_with_cid:
            if r["matches_new_cid"]:
                wo_issue_date = r["modified_on_formatted"]
                break
        
        # لو مفيش تطابق، ناخد التاريخ من أحدث Resource في القائمة
        if not wo_issue_date:
            wo_issue_date = resources_with_cid[0]["modified_on_formatted"]

    return ordered, wo_issue_date


def safe_pdf_path(order, filename):
    folder = os.path.join("WO_PDFs", str(order))
    os.makedirs(folder, exist_ok=True)

    clean_name = (filename or "WO.pdf").replace("/", "_").replace("\\", "_")
    if not clean_name.lower().endswith(".pdf"):
        clean_name = f"{clean_name}.pdf"

    return os.path.join(folder, clean_name)


def download_first_available_pdf(deps, session, docs, order):
    for activity in docs:
        notes = deps.get_notes_by_document(session, activity.get("activityid"))
        pdfs = deps.get_pdfs_from_notes(notes)

        for pdf in pdfs:
            file_path = safe_pdf_path(order, pdf.get("filename"))

            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path

            if deps.download_pdf(session, pdf.get("annotationid"), file_path):
                return file_path

    return ""


def find_work_order_pdf(deps, session, order, resources, result, debug=False):
    # استلام القيمتين: قائمة الـ IDs وتاريخ الـ Issue
    ordered_rr_ids, wo_issue_date = resource_ids_for_pdf(resources, result)
    
    for rr_id in ordered_rr_ids:
        full_data = deps.get_resource_full_data(session, rr_id)
        activities = full_data.get("te_resourceregistry_ActivityPointers", [])
        docs = ordered_document_activities(activities)

        if not docs:
            docs = ordered_document_activities(
                deps.get_documents_by_resource(session, rr_id)
            )

        pdf_path = download_first_available_pdf(deps, session, docs, order)
        if pdf_path:
            # ارجاع مسار الـ PDF مع تاريخ الـ Issue
            return pdf_path, wo_issue_date

    # لو ملفش لقى PDF
    return "", wo_issue_date