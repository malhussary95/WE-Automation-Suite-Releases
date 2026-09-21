import time

from services.wimax_service import open_wimax_page, fill_wimax, submit_wimax
from services.tedata_service import (
    validate_row,
    update_row,
    open_search_page,
    open_fiber_search_page,
    search_by_cid,
    search_by_order_id,
    open_edit_page,
)
from services.ftth_service import open_ftth_page, fill_ftth, submit_ftth
from services.fiber_service import FiberService


def process_rows(df, driver, action, service_type, logger,
                 selected_fields=None, check_map=None,
                 progress_callback=None, stop_flag=None):

    fiber = None  # ✅ هنستخدمه مرة واحدة

    for idx, row in df.iterrows():

        if stop_flag and stop_flag():
            logger("🛑 Stopped by user")
            break

        if action == "update":
            order_id = str(row.get("Order Id", "")).strip()

            if service_type == "fiber" and not order_id:
                logger(f"â© Skipping row {idx} (No Order Id)")
                continue

            cid = str(row.get("Circuit ID", "")).strip() or order_id or "N/A"

        elif action in ["validate", "update"]:
            cid = str(row.get("Circuit ID", "")).strip()

            if not cid:
                logger(f"⏩ Skipping row {idx} (No CID)")
                continue
        else:
            cid = "N/A"

        try:
            logger(f"🔍 Processing {cid}")

            # ================= ADD =================
            if action == "add":

                if service_type == "wimax":
                    open_wimax_page(driver)
                    fill_wimax(driver, row)
                    submit_wimax(driver)

                elif service_type == "ftth":
                    open_ftth_page(driver)
                    fill_ftth(driver, row)

                    # 🔥 هنا التعديل
                    success = submit_ftth(driver)

                    df.loc[idx, "Status"] = "Success" if success else "Failed"

                    # 🔥 Logging
                    if success:
                        logger(f"✅ FTTH Added: {row.get('Order Id')}")
                    else:
                        logger(f"❌ FTTH Failed: {row.get('Order Id')}")

                elif service_type == "fiber":

                    if fiber is None:
                        fiber = FiberService(driver, logger)

                    fiber.open_page()
                    fiber.fill_form(row)
                    fiber.submit()

                elif service_type == "shdsl":
                    logger("⚠️ SHDSL not implemented yet")

                elif service_type == "vdsl":
                    logger("⚠️ VDSL not implemented yet")

            # ================= VALIDATE =================
            elif action == "validate":
                validate_row(driver, row, df, idx, logger, check_map)

            # ================= UPDATE =================
            elif action == "update":
                if service_type == "fiber":
                    if fiber is None:
                        fiber = FiberService(driver, logger)

                    open_fiber_search_page(driver)
                    search_by_order_id(driver, order_id)
                    open_edit_page(driver)
                    fiber.fill_form(row)
                    fiber.submit()
                    df.loc[idx, "Status"] = "Updated"
                    logger(f"âœ… Fiber Updated: {order_id}")

                else:
                    logger(f"{service_type.upper()} update not implemented yet")
                    df.loc[idx, "Status"] = "Not Implemented"

            logger("✅ Done")

        except Exception as e:
            logger(f"❌ Error: {e}")
            df.loc[idx, "Status"] = "Error"

        if progress_callback:
            progress_callback(idx + 1)

        time.sleep(1)
