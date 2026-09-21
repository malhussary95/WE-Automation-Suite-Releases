from ecrm_extractor.fields import (
    BRANCH_JSON_REQUIRED_FIELDS,
    CUSTOMER_JSON_REQUIRED_FIELDS,
    IB_REQUIRED_FIELDS,
    RESOURCE_REQUIRED_FIELDS,
    RESULT_REQUIRED_FIELDS,
    SO_REQUIRED_FIELDS,
    USER_JSON_REQUIRED_FIELDS,
)


def has_any_selected(selected, field_names):
    return bool(selected.intersection(field_names))


def resolve_order_from_cid(session, cid, deps):
    cid = str(cid).strip()
    if not cid:
        return None

    if hasattr(deps, "get_resources_by_cids"):
        resources = deps.get_resources_by_cids(session, [cid])
    else:
        resources = deps.get_resource_by_cid(session, cid)

    if resources:
        try:
            # ترتيب الموارد تنازلياً حسب تاريخ الإنشاء لضمان الحصول على أحدث ORD
            resources = sorted(
                resources,
                key=lambda x: x.get("createdon") or "",
                reverse=True
            )
        except:
            pass

    for resource in resources:
        # محاولة البحث عن رقم الطلب في أكثر من حقل محتمل
        order = (
            resource.get("te_requestnumber") or 
            resource.get("new_orderlinenumberid") or
            resource.get("_te_serviceorderid_value@OData.Community.Display.V1.FormattedValue")
        )
        if order:
            return str(order).strip()

    return None


def resolve_orders_from_cids(session, cid_values, deps):
    orders = []
    seen_orders = set()
    clean_cids = list(
        dict.fromkeys(
            str(cid).strip()
            for cid in cid_values
            if str(cid).strip()
        )
    )

    if hasattr(deps, "get_resources_by_cids"):
        resources_by_cid = {cid: [] for cid in clean_cids}
        resources = deps.get_resources_by_cids(session, clean_cids)

        for resource in resources:
            cid = str(resource.get("te_circuitid") or "").strip()
            if cid in resources_by_cid:
                resources_by_cid[cid].append(resource)

        for cid in clean_cids:
            for resource in resources_by_cid.get(cid, []):
                order = resource.get("new_orderlinenumberid")

                if order and order not in seen_orders:
                    orders.append(order)
                    seen_orders.add(order)
                    break

        return orders

    for cid in clean_cids:
        resources = deps.get_resource_by_cid(session, cid)

        for resource in resources:
            order = resource.get("new_orderlinenumberid")

            if order and order not in seen_orders:
                orders.append(order)
                seen_orders.add(order)
                break

    return orders


def load_service_order_data(session, order, mode, selected, deps, debug=False):
    if not debug and (not has_any_selected(selected, SO_REQUIRED_FIELDS) or mode != "ORDER"):
        return [], {}, {}, {}

    service_orders = deps.get_service_orders(session, order)
    so = deps.get_latest_commercial_so(service_orders)
    
    data_so = deps.get_latest_data_services_so(service_orders)

    migration_so = deps.get_latest_migration_esupport_so(service_orders)

    return service_orders, so, data_so, migration_so


def load_task_data(session, so, mode, selected, deps):

    if "Current Task" not in selected or not so or mode != "ORDER":
        return []

    # =====================================================
    # CHILD SERVICE ORDERS
    # =====================================================
    child_sos = deps.get_child_service_orders(
        session,
        so.get("te_serviceorderid", "")
    )

    child_so_ids = [
        x.get("te_serviceorderid")
        for x in child_sos
        if x.get("te_serviceorderid")
    ]

    return deps.get_tasks(
        session,
        so.get("te_serviceorderid", ""),
        child_so_ids
    )

def load_resource_data(session, order, selected, deps, debug=False):
    if not debug and not has_any_selected(selected, RESOURCE_REQUIRED_FIELDS):
        return []

    return deps.get_resources(session, order)



def load_installed_base_data(session, order, selected, deps, debug=False):

    if not debug and not has_any_selected(selected, IB_REQUIRED_FIELDS):
        return []

    return deps.get_installed_base(session, order)



def enrich_installed_base_if_needed(session, installed, order, selected, deps, debug=False):
    if not debug and not has_any_selected(selected, IB_REQUIRED_FIELDS):
        return installed

    if not installed:
        installed = deps.get_installed_base(session, order)

    product_flat_ids = {
        row.get("_te_productflatid_value")
        for row in installed
        if row.get("_te_productflatid_value")
    }

    product_flats = deps.get_product_flats(session, product_flat_ids)

    return deps.enrich_installed_with_speed(installed, product_flats)

def build_resource_result(
    session,
    resources,
    so,
    migration_so,
    order,
    mode,
    selected,
    deps,
    debug=False
):

    # =====================================================
    # NO RESULT FIELDS SELECTED
    # =====================================================
    if not has_any_selected(selected, RESULT_REQUIRED_FIELDS):
        return {}

    # =====================================================
    # TARGET SO
    # =====================================================
    target_so = migration_so or so

    # =====================================================
    # DEFAULT RESOURCES
    # =====================================================
    filtered_resources = resources

    # =====================================================
    # LOAD SO COMPONENTS
    # =====================================================
    if target_so:

        so_id = target_so.get("te_serviceorderid")

        if so_id:
            try:
                component_resources = (
                    deps.get_service_order_components(
                        session,
                        so_id
                    ) or []
                )

                # نحتفظ بكل Resources الخاصة بالأوردر
                # ونضيف إليها Service Order Components
                # بدون تكرار نفس Resource Registry ID

                combined = []
                seen_ids = set()

                for r in resources or []:
                    rid = (
                        r.get("te_resourceregistryid")
                        or r.get("resourceid")
                        or r.get("te_name")
                    )

                    rid = str(rid or "").strip()

                    if rid and rid in seen_ids:
                        continue

                    if rid:
                        seen_ids.add(rid)

                    combined.append(r)

                for r in component_resources:
                    rid = (
                        r.get("te_resourceregistryid")
                        or r.get("resourceid")
                        or r.get("te_name")
                    )

                    rid = str(rid or "").strip()

                    if rid and rid in seen_ids:
                        continue

                    if rid:
                        seen_ids.add(rid)

                    combined.append(r)

                filtered_resources = combined

            except Exception:
                filtered_resources = resources

    # =====================================================
    # ORDER MODE
    # =====================================================
    if mode == "ORDER":

        return deps.extract_old_new_from_so(
            filtered_resources,
            target_so,
            order,
            debug=debug
        )

    # =====================================================
    # OTHER MODES
    # =====================================================
    return deps.extract_full_data(filtered_resources)


def load_customer_json(session, order, so, installed, selected, deps, debug=False):
    customer_id = so.get("_te_customernameaccountid_value")

    # Fallback to installed base if SO is missing
    if not customer_id and installed:
        for item in installed:
            customer_id = item.get("_customerid_value")
            if customer_id: break

    if not debug and (not has_any_selected(selected, CUSTOMER_JSON_REQUIRED_FIELDS) or not customer_id):
        return {}

    return deps.get_account_full_json(session, customer_id)


def load_user_json(session, order, customer_json, selected, deps, debug=False):
    user_id = customer_json.get("_te_accountmanagersystemuserid_value")

    if not debug and (not has_any_selected(selected, USER_JSON_REQUIRED_FIELDS) or not user_id):
        return {}

    return deps.get_user_full_json(session, user_id)


def load_branch_json(session, order, so, installed, selected, deps, debug=False):
    branch_id = so.get("_te_branchnameaccountid_value")

    # Fallback to installed base if SO is missing
    if not branch_id and installed:
        for item in installed:
            branch_id = item.get("_te_branchaccountid_value")
            if branch_id: break

    if not debug and (not has_any_selected(selected, BRANCH_JSON_REQUIRED_FIELDS) or not branch_id):
        return {}

    return deps.get_account_full_json(session, branch_id)



def load_commercial_data(session, order, selected, deps, debug=False):

    # لأن Order Status بقى بيعتمد عليها
    if not debug and "Order Status" not in selected:
        return []

    return deps.get_commercial_order_lines(session, order)
