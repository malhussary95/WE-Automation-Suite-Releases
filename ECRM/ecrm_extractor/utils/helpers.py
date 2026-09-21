def has_any_selected(selected, required_fields):

    return any(
        field in selected
        for field in required_fields
    )