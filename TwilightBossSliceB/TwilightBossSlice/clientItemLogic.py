# -*- coding: utf-8 -*-
import TwilightBossSlice.maze_map_logic as maze_map_logic


CUSTOM_FILLED_MAGIC_MAP_NAMES = frozenset(
    (
        "tf_slice:filled_magic_map",
        "filled_magic_map",
    )
)
LEGACY_NATIVE_MAP_NAMES = frozenset(
    ("minecraft:filled_map", "filled_map")
)
TF_MAGIC_MAP_EXTRA_ID_PREFIXES = (
    "tfmm:v1:",
    "tfmm:v2:",
    "tfmm:v3:",
)

ITEM_NAME_KEYS = (
    "newItemName",
    "itemName",
    "identifier",
    "name",
)

EVENT_ITEM_KEYS = (
    "itemDict",
    "newItemDict",
    "newItem",
    "item",
)


def item_name(item):
    if not isinstance(item, dict):
        return ""
    for key in ITEM_NAME_KEYS:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def item_extra_id(item):
    if not isinstance(item, dict):
        return ""
    for key in ("newItemExtraId", "extraId"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


def is_filled_magic_map(item):
    name = item_name(item)
    if name in ("tf_slice:filled_maze_map", "filled_maze_map"):
        return maze_map_logic.decode_identity(item_extra_id(item)) is not None
    if name in CUSTOM_FILLED_MAGIC_MAP_NAMES:
        return True
    if name not in LEGACY_NATIVE_MAP_NAMES:
        return False
    return item_extra_id(item).startswith(
        TF_MAGIC_MAP_EXTRA_ID_PREFIXES
    )


def filled_magic_map_signature(item):
    """Return the stable identity used to detect a held-map replacement."""
    if not is_filled_magic_map(item):
        return None
    return "%s|%s" % (item_name(item), item_extra_id(item))


def should_show_held_map(held, perspective):
    """Keep the first-person map sheet out of third-person camera modes."""
    if not bool(held):
        return False
    if perspective is None:
        return True
    try:
        return int(perspective) == 0
    except (TypeError, ValueError):
        return True


def resolve_held_map_state(
    server_held,
    observed_items=(),
    observation_succeeded=False,
    event_main_held=None,
):
    """Prefer fresh local item evidence over a delayed server held flag."""
    locally_held = any(
        is_filled_magic_map(item) for item in observed_items or ()
    )
    if event_main_held is not None:
        return bool(event_main_held) or locally_held
    if observation_succeeded:
        return locally_held
    return bool(server_held)


def event_holds_filled_magic_map(args):
    if not isinstance(args, dict):
        return False
    if is_filled_magic_map(args):
        return True
    for key in EVENT_ITEM_KEYS:
        if is_filled_magic_map(args.get(key)):
            return True
    return False
