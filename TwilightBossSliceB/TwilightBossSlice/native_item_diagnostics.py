# -*- coding: utf-8 -*-
"""Bounded breadcrumbs around native held-item registry calls."""


TRACE_PREFIX = "[TF_NATIVE_ITEM_DIAG]"
DETAILED_CALL_LIMIT = 4096
SAMPLE_INTERVAL = 300
ENABLED = False


def should_trace(sequence, enabled=None):
    if enabled is None:
        enabled = ENABLED
    if not enabled:
        return False
    try:
        sequence = int(sequence)
    except (TypeError, ValueError):
        return False
    if sequence <= 0:
        return False
    return (
        sequence <= DETAILED_CALL_LIMIT
        or sequence % SAMPLE_INTERVAL == 0
    )


def _safe_token(value, fallback="none"):
    if value is None:
        return fallback
    try:
        text = str(value)
    except Exception:
        return "unprintable"
    text = "_".join(text.split())
    text = text.replace("=", "_")
    return text[:96] or fallback


def _item_name(item):
    if not isinstance(item, dict):
        return "none"
    for key in ("itemName", "newItemName"):
        value = item.get(key)
        if value:
            return _safe_token(value)
    return "none"


def begin_line(side, sequence, hand, tick):
    return (
        "%s phase=begin side=%s seq=%d hand=%s tick=%d"
        % (
            TRACE_PREFIX,
            _safe_token(side, "unknown"),
            int(sequence),
            _safe_token(hand, "unknown"),
            int(tick),
        )
    )


def end_line(
    side,
    sequence,
    hand,
    tick,
    elapsed_ms,
    item=None,
    error=None,
):
    try:
        elapsed_ms = max(0, int(float(elapsed_ms)))
    except (TypeError, ValueError):
        elapsed_ms = 0
    error_name = (
        "none"
        if error is None
        else _safe_token(error.__class__.__name__, "unknown")
    )
    return (
        "%s phase=end side=%s seq=%d hand=%s tick=%d "
        "success=%d item=%s elapsedMs=%d error=%s"
        % (
            TRACE_PREFIX,
            _safe_token(side, "unknown"),
            int(sequence),
            _safe_token(hand, "unknown"),
            int(tick),
            int(error is None),
            _item_name(item),
            elapsed_ms,
            error_name,
        )
    )
