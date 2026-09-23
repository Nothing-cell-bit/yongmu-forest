# -*- coding: utf-8 -*-
"""Map public Twilight wood items onto complete vanilla block templates."""


SHAPE_SUFFIXES = (
    "stairs",
    "slab",
    "button",
    "fence",
    "fence_gate",
    "pressure_plate",
    "door",
    "trapdoor",
    "sign",
    "wall_sign",
    "hanging_sign",
    "wall_hanging_sign",
    "banister",
)
PLAYER_VISIBLE_NATIVE_SUFFIXES = (
    "stairs",
    "slab",
    "button",
    "fence",
    "fence_gate",
    "pressure_plate",
    "door",
    "trapdoor",
    "sign",
    "hanging_sign",
)
CANOPY_NATIVE_SUFFIXES = (
    "stairs",
    "slab",
    "button",
    "fence",
    "fence_gate",
    "pressure_plate",
    "door",
    "trapdoor",
)
WOOD_TEMPLATE_FAMILIES = (
    ("dark", "dark_oak", SHAPE_SUFFIXES),
    ("mangrove", "mangrove", SHAPE_SUFFIXES),
    ("canopy", "cherry", CANOPY_NATIVE_SUFFIXES),
)
PUBLIC_CUSTOM_WOOD_ITEMS = (
    "tf_slice:dark_banister",
    "tf_slice:mangrove_banister",
    "tf_slice:canopy_banister",
    "tf_slice:canopy_bookshelf",
    "tf_slice:canopy_chest",
)


def _build_adapters():
    result = {}
    for family, vanilla_family, suffixes in WOOD_TEMPLATE_FAMILIES:
        for suffix in suffixes:
            if suffix == "banister":
                continue
            vanilla_suffix = {
                "wall_sign": "sign",
                "wall_hanging_sign": "hanging_sign",
            }.get(suffix, suffix)
            target = "minecraft:%s_%s" % (
                vanilla_family,
                vanilla_suffix,
            )
            result["tf_slice:%s_%s" % (family, suffix)] = target
    return result


VANILLA_BLOCK_ADAPTERS = _build_adapters()


def _build_player_visible_adapters():
    result = {}
    for family, vanilla_family, unused_suffixes in WOOD_TEMPLATE_FAMILIES:
        visible_suffixes = (
            CANOPY_NATIVE_SUFFIXES
            if family == "canopy"
            else PLAYER_VISIBLE_NATIVE_SUFFIXES
        )
        for suffix in visible_suffixes:
            result["tf_slice:%s_%s" % (family, suffix)] = (
                "minecraft:%s_%s" % (vanilla_family, suffix)
            )
        if family != "canopy":
            result["tf_slice:%s_wall_sign" % family] = (
                "minecraft:%s_sign" % vanilla_family
            )
            result["tf_slice:%s_wall_hanging_sign" % family] = (
                "minecraft:%s_hanging_sign" % vanilla_family
            )
    return result


PLAYER_VISIBLE_WOOD_ADAPTERS = _build_player_visible_adapters()
MIGRATED_WOOD_ALIASES = frozenset(PLAYER_VISIBLE_WOOD_ADAPTERS)
PUBLIC_NATIVE_WOOD_ITEMS = tuple(
    sorted(set(PLAYER_VISIBLE_WOOD_ADAPTERS.values()))
)


def player_visible_wood_item(item_name):
    """Return the public native item for a legacy custom wood alias."""
    item_name = str(item_name)
    return PLAYER_VISIBLE_WOOD_ADAPTERS.get(item_name, item_name)


def source_block_name(args):
    return str(args.get("fullName", args.get("blockName", "")))


def item_stack_name(item):
    if not item:
        return ""
    return str(
        item.get("newItemName")
        or item.get("itemName")
        or item.get("name")
        or ""
    )


def converted_vanilla_stack(item):
    """Return a clean vanilla stack for a public adapter item."""
    target = VANILLA_BLOCK_ADAPTERS.get(item_stack_name(item))
    if target is None:
        return None
    return {
        "itemName": target,
        "newItemName": target,
        "count": max(1, int(item.get("count", 1))),
        "auxValue": int(item.get("auxValue", 0)),
    }


def adapt_placement_event(args):
    """Rewrite a try-place event so the engine runs vanilla placement logic."""
    target = VANILLA_BLOCK_ADAPTERS.get(source_block_name(args))
    if target is None:
        return None
    args["fullName"] = target
    # Kept in sync for older 3.x event payload consumers.
    args["blockName"] = target
    return target
