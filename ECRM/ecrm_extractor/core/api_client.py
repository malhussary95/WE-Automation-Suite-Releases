import base64
import os

import requests

from ecrm_extractor.config import BASE_URL, ECRM_BASE_URL


REQUEST_TIMEOUT = 60


def _get_json(session, url, params=None, default=None):
    try:
        res = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        return default if default is not None else {}

    if res.status_code == 200:
        return res.json()

    return default if default is not None else {}


def _get_values(session, url, params=None):
    return _get_json(session, url, params=params, default={}).get("value", [])


def _get_values_with_status(session, url, params=None):
    try:
        res = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        return None, None

    if res.status_code == 200:
        return res.json().get("value", []), res.status_code

    return None, res.status_code


def _guid_filters(field_name, guid):
    clean_guid = str(guid).strip("{}")
    return [
        f"{field_name} eq {clean_guid}",
        f"{field_name} eq '{clean_guid}'",
    ]

def get_resource_by_cid(session, cid):
    cid = str(cid).strip()

    url = f"{BASE_URL}/te_resourceregistries"
    params = {
        "$filter": f"te_circuitid eq '{cid}'",
        "$select": "te_resourceregistryid,te_name,te_circuitid,createdon,modifiedon,statecode,statuscode,new_orderlinenumberid,te_notes,te_esptstatuscode,te_infrastructureavailabilitystatusnewcode"
    }
    return _get_values(session, url, params=params)


def _escape_odata_string(value):
    return str(value).strip().replace("'", "''")


def get_resources_by_cids(session, cid_values, chunk_size=20):
    clean_cids = []
    seen = set()

    for cid in cid_values:
        clean_cid = str(cid).strip()
        if not clean_cid or clean_cid in seen:
            continue
        clean_cids.append(clean_cid)
        seen.add(clean_cid)

    if not clean_cids:
        return []

    url = f"{BASE_URL}/te_resourceregistries"
    all_resources = []

    for i in range(0, len(clean_cids), chunk_size):
        chunk = clean_cids[i:i + chunk_size]
        filters = [
            f"te_circuitid eq '{_escape_odata_string(cid)}'"
            for cid in chunk
        ]
        params = {
            "$filter": " or ".join(filters),
            "$select": "te_resourceregistryid,te_name,te_circuitid,createdon,modifiedon,statecode,statuscode,new_orderlinenumberid,te_notes,te_esptstatuscode,te_infrastructureavailabilitystatusnewcode",
        }
        all_resources.extend(_get_values(session, url, params=params))

    return all_resources


def get_service_order_by_soid(session, so_id):
    so_id = str(so_id).strip()

    url = f"{BASE_URL}/te_serviceorders"
    params = {
        "$filter": f"te_soid eq '{so_id}'"
    }
    return _get_values(session, url, params=params)


def get_resource_full_data(session, rr_id):
    """
    Get full Resource data with related Activities + Attachments
    """

    url = f"{BASE_URL}/te_resourceregistries({rr_id})"

    params = {
        "$expand": "te_resourceregistry_ActivityPointers"
    }
    return _get_json(session, url, params=params, default={})


def get_documents_by_resource(session, rr_id):
    if not rr_id:
        return []

    url = f"{BASE_URL}/activitypointers"
    filters = [
        f"{filter_value} and activitytypecode eq 'te_document'"
        for filter_value in _guid_filters("_regardingobjectid_value", rr_id)
    ]

    for filter_value in filters:
        params = {
            "$filter": filter_value,
            "$select": "activityid,subject,activitytypecode,modifiedon,createdon",
            "$orderby": "modifiedon desc"
        }

        values, status_code = _get_values_with_status(session, url, params=params)
        if status_code == 200:
            return values

    return []


def get_api(session, url):
    return _get_values(session, url)


def get_user_full_json(session, user_id):
    url = f"{BASE_URL}/systemusers({user_id})"
    return _get_json(session, url, default={})


def get_notes_by_document(session, activity_id):

    url = f"{BASE_URL}/annotations"

    if not activity_id:
        return []

    filters = _guid_filters("_objectid_value", activity_id)

    for filter_value in filters:
        params = {
            "$filter": filter_value,
            "$select": "annotationid,filename,mimetype,createdon,isdocument,filesize",
            "$orderby": "createdon desc"
        }

        values, status_code = _get_values_with_status(session, url, params=params)
        if status_code == 200:
            return values

    return []


def get_notes(session, entity_id):
    url = f"{BASE_URL}/annotations"

    if not entity_id:
        return []

    filters = _guid_filters("_objectid_value", entity_id)

    for filter_value in filters:
        params = {
            "$filter": filter_value,
            "$select": "annotationid,notetext,filename,createdon,modifiedon",
            "$orderby": "modifiedon desc"
        }
        values, status_code = _get_values_with_status(session, url, params=params)
        if status_code == 200:
            return values
    return []


def _download_pdf_from_documentbody(session, annotation_id, file_path):
    url = f"{BASE_URL}/annotations({annotation_id})"
    params = {
        "$select": "documentbody,filename,mimetype"
    }

    try:
        r = session.get(url, params=params, timeout=REQUEST_TIMEOUT)

        if r.status_code != 200:
            return False

        data = r.json()
        documentbody = data.get("documentbody")

        if not documentbody:
            return False

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(base64.b64decode(documentbody))

        return True

    except Exception as e:
        return False


def download_pdf(session, annotation_id, file_path):

    url = (
        f"{ECRM_BASE_URL}"
        "Activities/Attachment/download.aspx"
        "?AttachmentType=5"
        "&IsNotesTabAttachment=1"
        f"&AttachmentId={annotation_id}"
    )

    try:
        r = session.get(url, stream=True, timeout=REQUEST_TIMEOUT)

        if r.status_code != 200:
            return _download_pdf_from_documentbody(session, annotation_id, file_path)

        content_type = r.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            return _download_pdf_from_documentbody(session, annotation_id, file_path)

        os.makedirs(
            os.path.dirname(file_path),
            exist_ok=True
        )

        wrote_bytes = 0
        with open(file_path, "wb") as f:
            for chunk in r.iter_content(1024):
                if chunk:
                    f.write(chunk)
                    wrote_bytes += len(chunk)

        if wrote_bytes == 0:
            return False

        return True

    except Exception as e:
        return _download_pdf_from_documentbody(session, annotation_id, file_path)


def get_service_orders(session, order):
    url = f"{BASE_URL}/te_serviceorders?$filter=te_orderlinenumber eq '{order}'"
    return get_api(session, url)


def get_resources_by_ord(session, ord_number):
    ord_number = str(ord_number).strip()

    url = f"{BASE_URL}/te_resourceregistries"
    params = {
        "$filter": f"te_requestnumber eq '{ord_number}'"
    }
    return _get_values(session, url, params=params)


def get_installed_base_enriched(session, ib_id):
    url = f"{BASE_URL}/contractdetails({ib_id})?$expand=te_productflatid"
    return _get_json(session, url, default={})


def get_product_flat(session, productflat_id):
    url = f"{BASE_URL}/te_productflats({productflat_id})"
    return _get_json(session, url, default={})



def get_resources(session, order):

    url = (
        f"{BASE_URL}/te_resourceregistries?"
        f"$filter=new_orderlinenumberid eq '{order}'"
    )

    return get_api(session, url)



def inspect_entity(session, entity_name):

    url = f"{BASE_URL}/{entity_name}"

    params = {
        "$top": 1
    }

    try:

        r = session.get(url, params=params, timeout=30)

        if r.status_code != 200:
            return

        data = r.json()

        values = data.get("value", [])

        if not values:
            return

    except Exception as e:
        pass


def get_product_flats(session, product_flat_ids):
    if not product_flat_ids:
        return {}

    ids = list(product_flat_ids)
    results = {}

    for i in range(0, len(ids), 20):
        chunk = ids[i:i+20]

        flt = " or ".join([f"te_productflatid eq {pid}" for pid in chunk])

        url = f"{BASE_URL}/te_productflats?$filter={flt}"

        data = get_api(session, url)

        for row in data:
            results[row.get("te_productflatid")] = row

    return results


def get_installed_base(session, order):
    order = str(order).strip().replace("'", "''")

    # Read the Installed Base Line record itself.
    # Status must come from contractdetails.statuscode, not Product Flat.
    url = f"{BASE_URL}/contractdetails"
    params = {
        "$filter": f"te_orderlinenumber eq '{order}'",
        "$select": (
            "contractdetailid,te_orderlinenumber,te_producttypecode,statecode,"
            "statuscode,createdon,modifiedon,_productid_value,"
            "_te_productflatid_value"
        ),
        "$orderby": "createdon desc",
    }
    return _get_values(session, url, params=params)


def get_commercial_order_lines(session, order):

    order = str(order).strip()

    url = f"{BASE_URL}/salesorderdetails"

    params = {
        "$filter": f"te_orderlinenumber eq '{order}'",
    }

    return _get_values(session, url, params=params)



def get_child_service_orders(session, so_id):

    if not so_id:
        return []

    so_id = str(so_id).strip("{}")

    url = (
        f"{BASE_URL}/te_serviceorders"
        f"?$filter=_te_parentserviceorderid_value eq '{so_id}'"
    )

    return get_api(session, url)


def get_tasks(session, so_id, child_so_ids=None):

    if not so_id:
        return []

    # =====================================================
    # ALL SERVICE ORDERS IDS
    # =====================================================
    all_so_ids = [str(so_id).strip("{}")]

    if child_so_ids:
        all_so_ids.extend(
            str(x).strip("{}")
            for x in child_so_ids
            if x
        )

    # remove duplicates
    all_so_ids = list(dict.fromkeys(all_so_ids))

    # =====================================================
    # GET TASKS
    # =====================================================
    all_tasks = []

    for current_so_id in all_so_ids:

        url = (
            f"{BASE_URL}/activitypointers"
            f"?$filter="
            f"_regardingobjectid_value eq '{current_so_id}' "
            f"and activitytypecode eq 'task'"
            f"&$orderby=createdon desc"
        )

        data = get_api(session, url)

        if data:
            all_tasks.extend(data)

    # =====================================================
    # REMOVE DUPLICATES
    # =====================================================
    unique = {}

    for task in all_tasks:

        activity_id = task.get("activityid")

        if activity_id:
            unique[activity_id] = task

    return list(unique.values())

def get_account_full_json(session, account_id):
    url = f"{BASE_URL}/accounts({account_id})"
    return _get_json(session, url, default={})


def get_port_full_data(session, port_id):
    url = f"{BASE_URL}/te_resourceregistries({port_id})"
    params = {
        "$expand": "te_resourceregistry_ActivityPointers"
    }
    return _get_json(session, url, params=params, default={})


def inspect_service_order(session, so_guid):
    url = f"{BASE_URL}/te_serviceorders({so_guid})"
    params = {
        "$top": 1
    }
    return _get_json(session, url, params=params)

def get_service_order_components(session, so_guid):
    fetchxml = f"""
    <fetch version="1.0" mapping="logical" distinct="false">
        <entity name="te_serviceorder">
            <attribute name="te_serviceorderid"/>
            <attribute name="te_changeactioncode"/>
            <attribute name="te_name"/>
            <link-entity
                name="te_resourceregistry"
                from="te_resourceregistryid"
                to="te_resourceregistryid"
                alias="rr"
                link-type="outer">
                <attribute name="te_circuitid"/>
                <attribute name="te_requestnumber"/>
                <attribute name="te_resourceramilycode"/>
                <attribute name="te_resourcecomponentcode"/>
                <attribute name="te_esptstatuscode"/>
                <attribute name="te_infrastructureavailabilitystatusnewcode"/>
            </link-entity>
            <link-entity
                name="te_serviceorder"
                from="te_serviceorderid"
                to="te_parentserviceorderid"
                alias="parent">
                <filter>
                    <condition
                        attribute="te_serviceorderid"
                        operator="eq"
                        value="{so_guid}"/>
                </filter>
            </link-entity>
        </entity>
    </fetch>
    """
    return _get_values(
        session,
        f"{BASE_URL}/te_serviceorders",
        params={
            "fetchXml": fetchxml
        }
    )



def get_resources_by_service_order(session, so_value):

    so_value = str(so_value).strip()

    # =====================================================
    # GET SERVICE ORDER
    # =====================================================
    if "-" in so_value and len(so_value) > 30:
        url = f"{BASE_URL}/te_serviceorders({so_value})"
        so = _get_json(session, url, default={})
        if not so:
            return []
    else:
        service_orders = get_service_order_by_soid(
            session,
            so_value
        )
        if not service_orders:
            return []
        so = service_orders[0]

    # =====================================================
    # GET ORDER LINE
    # =====================================================
    order = str(
        so.get("te_orderlinenumber", "")
    ).strip()
    if not order:
        return []

    # =====================================================
    # GET RESOURCES
    # =====================================================
    resources = get_resources(
        session,
        order
    )
    return resources
