# -*- coding: utf-8 -*-
"""Pure state transitions for Twilight Forest banisters."""

BANISTER_BLOCKS = frozenset(
    (
        "tf_slice:dark_banister",
        "tf_slice:mangrove_banister",
        "tf_slice:canopy_banister",
    )
)
SHAPES = ("short", "tall", "connected")


def is_banister(block_name):
    return str(block_name) in BANISTER_BLOCKS


def is_axe(item_name):
    return str(item_name).split(":", 1)[-1].endswith("_axe")


def placement_states(block_above):
    return {
        "tf_slice:shape": (
            "connected" if is_banister(block_above) else "tall"
        ),
        "tf_slice:extended": False,
    }


def mode(states):
    states = states or {}
    shape = str(states.get("tf_slice:shape", "tall"))
    if shape not in SHAPES:
        shape = "tall"
    return shape, bool(states.get("tf_slice:extended", False))


def cycle_states(states):
    """Cycle SHORT -> TALL -> CONNECTED, toggling extension at TALL.

    The upstream enum order is SHORT, TALL, CONNECTED.  Starting from the
    default TALL state therefore yields CONNECTED, SHORT, then TALL; arriving
    at TALL completes one full cycle and toggles the downward extension.
    """
    result = dict(states or {})
    shape, extended = mode(result)
    next_shape = SHAPES[(SHAPES.index(shape) + 1) % len(SHAPES)]
    result["tf_slice:shape"] = next_shape
    if next_shape == "tall":
        extended = not extended
    result["tf_slice:extended"] = extended
    return result


def connection_states(states, block_above):
    """Bridge NetEase neighbor events to the upstream vertical shapes."""
    result = dict(states or {})
    shape, unused_extended = mode(result)
    if is_banister(block_above) and shape == "tall":
        result["tf_slice:shape"] = "connected"
    elif not is_banister(block_above) and shape == "connected":
        result["tf_slice:shape"] = "tall"
    return result
