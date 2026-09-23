# -*- coding: utf-8 -*-
"""Pure placement rules shared by player-visible custom blocks."""

import copy
import math


CARDINAL_FACINGS = ("north", "east", "south", "west")
TROPHY_VARIANTS = (
    "naga",
    "lich",
    "hydra",
    "ur_ghast",
    "knight_phantom",
    "minoshroom",
    "quest_ram",
)
TROPHY_ITEM_TO_BLOCK = {
    "tf_slice:%s_trophy_item" % name: "tf_slice:%s_trophy" % name
    for name in TROPHY_VARIANTS
}
TROPHY_ITEM_NAMES = frozenset(TROPHY_ITEM_TO_BLOCK)
TROPHY_LEGACY_ITEM_NAMES = frozenset(TROPHY_ITEM_TO_BLOCK.values())
HUGE_LILY_QUADRANT_OFFSETS = {
    "nw": (0, 0),
    "ne": (1, 0),
    "se": (1, 1),
    "sw": (0, 1),
}
HUGE_LILY_SINGLE_CLEARANCE_OFFSETS = tuple(
    (x_offset, z_offset)
    for x_offset in (-1, 0, 1)
    for z_offset in (-1, 0, 1)
)


def facing_towards_player(yaw):
    """Return the block front that faces a player at the supplied yaw."""
    quarter_turn = int(round(float(yaw) / 90.0)) % 4
    return CARDINAL_FACINGS[quarter_turn]


def trophy_rotation_from_yaw(yaw):
    """Quantize a trophy to the four requested cardinal rotation segments."""
    return (
        int(math.floor(float(yaw) / 90.0 + 0.5)) * 4
    ) % 16


def trophy_block_for_face(item_name, face):
    """Select the hidden wall variant for horizontal placement faces."""
    item_name = str(item_name)
    floor_name = TROPHY_ITEM_TO_BLOCK.get(item_name)
    if floor_name is None and item_name in TROPHY_LEGACY_ITEM_NAMES:
        floor_name = item_name
    if floor_name is None:
        return None
    try:
        face = int(face)
    except (TypeError, ValueError):
        return None
    if face in (0, 1):
        return floor_name
    if face in (2, 3, 4, 5):
        return floor_name[: -len("_trophy")] + "_wall_trophy"
    return None


def split_trophy_for_head(carried_item, head_item):
    """Split one carried trophy for the empty armor-head slot."""
    carried_item = carried_item or {}
    if head_item:
        return None
    item_name = str(carried_item.get("itemName", ""))
    if item_name not in TROPHY_ITEM_NAMES | TROPHY_LEGACY_ITEM_NAMES:
        return None
    try:
        count = int(carried_item.get("count", 0))
    except (TypeError, ValueError):
        return None
    if count <= 0:
        return None
    equipped = copy.deepcopy(carried_item)
    equipped["count"] = 1
    remaining = copy.deepcopy(carried_item)
    remaining["count"] = count - 1
    return (remaining if remaining["count"] else None, equipped)


def floor_trophy_visual_yaw(rotation):
    """Return the baked/entity yaw for one ROTATION_16 trophy state."""
    try:
        rotation = int(rotation)
    except (TypeError, ValueError):
        rotation = 0
    return (22.5 * (rotation % 16)) % 360.0


def wall_trophy_visual_yaw(facing):
    """Match an entity-backed trophy visual to the baked wall block rotation."""
    return {
        "north": 0.0,
        "east": 90.0,
        "south": 180.0,
        "west": 270.0,
    }.get(str(facing), 0.0)


def ur_ghast_trophy_entity_yaw(baked_block_yaw):
    """Face back toward the placer on both axes; yaw keeps its rotation sign."""
    try:
        baked_block_yaw = float(baked_block_yaw)
    except (TypeError, ValueError):
        baked_block_yaw = 0.0
    return (180.0 + baked_block_yaw) % 360.0


def effective_trophy_rotation(states):
    states = states or {}
    try:
        rotation = int(states.get("tf_slice:rotation", 0)) % 16
    except (TypeError, ValueError):
        rotation = 0
    if rotation:
        return (
            int(math.floor(float(rotation) / 4.0 + 0.5)) * 4
        ) % 16
    return {
        "south": 0,
        "west": 4,
        "north": 8,
        "east": 12,
    }.get(str(states.get("minecraft:cardinal_direction", "south")), 0)


def effective_trophy_facing(states):
    states = states or {}
    facing = str(states.get("tf_slice:facing", "north"))
    if facing != "north":
        return facing
    return {
        "south": "north",
        "west": "east",
        "north": "south",
        "east": "west",
    }.get(str(states.get("minecraft:cardinal_direction", "south")), "north")


def trophy_event_block_name(event_name, live_block_name):
    """Prefer the live block when NetEase omits/replaces the destroy payload name."""
    event_name = str(event_name or "")
    if event_name and event_name not in (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
    ):
        return event_name
    return str(live_block_name or "")


def _rotated_quadrant_offset(quadrant, facing):
    x_value, z_value = HUGE_LILY_QUADRANT_OFFSETS[str(quadrant)]
    turns = CARDINAL_FACINGS.index(str(facing))
    for unused in range(turns):
        x_value, z_value = 1 - z_value, x_value
    return x_value, z_value


def huge_lily_layout(anchor, facing):
    """Map four world positions to the quadrant blocks of one 2x2 pad."""
    anchor = tuple(int(value) for value in anchor)
    facing = str(facing)
    result = {}
    for quadrant in ("nw", "ne", "se", "sw"):
        x_offset, z_offset = _rotated_quadrant_offset(quadrant, facing)
        position = (
            anchor[0] + x_offset,
            anchor[1],
            anchor[2] + z_offset,
        )
        result[position] = {
            "quadrant": quadrant,
            "facing": facing,
            "block": "tf_slice:huge_lily_pad_%s" % quadrant,
        }
    return result


def huge_lily_anchor(position, quadrant, facing):
    """Recover the north-west layout anchor from any member quadrant."""
    position = tuple(int(value) for value in position)
    x_offset, z_offset = _rotated_quadrant_offset(quadrant, facing)
    return (
        position[0] - x_offset,
        position[1],
        position[2] - z_offset,
    )


def huge_lily_single_clearance_positions(anchor):
    """Return the full 3x3 water footprint around one large visual pad."""
    anchor = tuple(int(value) for value in anchor)
    return tuple(
        (
            anchor[0] + x_offset,
            anchor[1],
            anchor[2] + z_offset,
        )
        for x_offset, z_offset in HUGE_LILY_SINGLE_CLEARANCE_OFFSETS
    )
