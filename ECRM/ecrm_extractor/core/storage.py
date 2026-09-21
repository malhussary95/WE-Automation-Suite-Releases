import json
import os


def save_debug_json(folder_name, order, file_name, data, indent=4):
    folder = os.path.join(folder_name, str(order))
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{file_name}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

    return file_path


def save_resource_json(order, cid, data):
    return save_debug_json("RR_DEBUG", order, cid, data)


def save_user_json(order, user_id, data):
    return save_debug_json("USER_DEBUG", order, user_id, data)


def save_account_json(order, account_id, data):
    return save_debug_json("ACCOUNT_DEBUG", order, account_id, data)


def save_branch_json(order, branch_id, data):
    return save_debug_json("BRANCH_DEBUG", order, branch_id, data)


def log_resources(order, resources):
    os.makedirs("DEBUG_LOGS", exist_ok=True)

    with open(f"DEBUG_LOGS/{order}_resources.txt", "w", encoding="utf-8") as f:
        for r in resources:
            f.write(f"{r}\n\n")


def save_json_debug(order, rr_id, data, name):
    folder = "DEBUG_JSON"
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{order}_{name}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({
            "order": order,
            "rr_id": rr_id,
            "data": data
        }, f, indent=2, ensure_ascii=False)


def save_json(order, name, data):
    """Save JSON to RR_DEBUG/{order}/{name}.json"""
    folder = os.path.join("RR_DEBUG", str(order))
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, f"{name}.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    return file_path