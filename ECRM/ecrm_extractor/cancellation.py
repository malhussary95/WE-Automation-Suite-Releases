class ExtractionCancelled(Exception):
    pass


def is_cancelled(gui):
    checker = getattr(gui, "is_cancelled", None)
    return bool(checker and checker())


def check_cancelled(gui):
    if is_cancelled(gui):
        raise ExtractionCancelled()
