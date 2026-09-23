# -*- coding: utf-8 -*-
"""Pure helpers for chat commands that must always produce visible feedback."""


def paginate_catalog(label, identifiers, max_chars=120):
    label = str(label)
    identifiers = [str(value) for value in identifiers or []]
    max_chars = max(48, int(max_chars))
    if not identifiers:
        return ["%s (0/0): none" % label]

    pages = []
    current = []
    # Reserve room for ``Label (99/99): `` so every final line stays under
    # NetEase's conservative notification length.
    payload_limit = max(16, max_chars - len(label) - 12)
    for identifier in identifiers:
        candidate = ", ".join(current + [identifier])
        if current and len(candidate) > payload_limit:
            pages.append(current)
            current = [identifier]
        else:
            current.append(identifier)
    if current:
        pages.append(current)

    total = len(pages)
    return [
        "%s (%d/%d): %s" % (label, index + 1, total, ", ".join(page))
        for index, page in enumerate(pages)
    ]


def safe_debug_locate(locator, ruin_id, position, radius):
    try:
        return locator(ruin_id, position, radius)
    except Exception as error:
        return False, "locate failed: %s" % error
