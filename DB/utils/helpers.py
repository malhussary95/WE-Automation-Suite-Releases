def safe_get(row, key):
    return str(row.get(key, "")).strip()