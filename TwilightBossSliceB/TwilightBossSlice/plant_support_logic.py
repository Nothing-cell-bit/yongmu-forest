# -*- coding: utf-8 -*-
"""Support rules for small plants; None means terrain is not readable yet."""

HANGING_PLANTS = frozenset((
    "tf_slice:root_strand", "tf_slice:torchberry_plant",
    "tf_slice:torchberry_plant_empty",
))
GROUND_PLANTS = frozenset(("tf_slice:fiddlehead", "tf_slice:mayapple"))
WATER_PLANTS = frozenset((
    "tf_slice:huge_water_lily", "tf_slice:huge_lily_pad",
    "tf_slice:huge_lily_pad_nw", "tf_slice:huge_lily_pad_ne",
    "tf_slice:huge_lily_pad_sw", "tf_slice:huge_lily_pad_se",
))
PLANTS = HANGING_PLANTS | GROUND_PLANTS | WATER_PLANTS | frozenset((
    "tf_slice:mushgloom", "tf_slice:fallen_leaves",
))
FIREFLY = "tf_slice:firefly"
# Firefly attachment enforcement is disabled at the user's request.
SUPPORTED_BLOCKS = PLANTS
# Facing points from the supporting block toward the bug (same as worldgen).
FIREFLY_SUPPORT_OFFSETS = {
    "north": (0, 0, 1), "south": (0, 0, -1),
    "west": (1, 0, 0), "east": (-1, 0, 0),
}
WATER = frozenset(("minecraft:water", "minecraft:flowing_water"))
AIR = frozenset(("minecraft:air", "minecraft:cave_air", "minecraft:void_air"))
SOIL = frozenset((
    "minecraft:grass", "minecraft:grass_block", "minecraft:dirt",
    "minecraft:coarse_dirt", "minecraft:podzol", "minecraft:mycelium",
    "minecraft:rooted_dirt", "minecraft:moss_block", "minecraft:farmland",
    "tf_slice:landmark_protected_grass",
))


def firefly_facing(face):
    try:
        return {2: "north", 3: "south", 4: "west", 5: "east"}.get(int(face))
    except (TypeError, ValueError):
        return None


def opposite_firefly_facing(facing):
    return {"north": "south", "south": "north", "west": "east", "east": "west"}.get(facing)


def support_position(plant, position, facing=None):
    if plant == FIREFLY:
        offset = FIREFLY_SUPPORT_OFFSETS.get(facing)
        if offset is None:
            return None
        return tuple(position[index] + offset[index] for index in range(3))
    return (position[0], position[1] + (1 if plant in HANGING_PLANTS else -1), position[2])


def named_support(plant, support):
    """Resolve named substrates first; other supports need a collision query."""
    if not support:
        return None
    if support in AIR or support in ("minecraft:lava", "minecraft:flowing_lava"):
        return False
    if plant in WATER_PLANTS:
        return support in WATER
    if plant == "tf_slice:fallen_leaves" and support in WATER:
        return True
    if support in WATER:
        return False
    if plant in GROUND_PLANTS:
        return support in SOIL
    # Cave generation also permits strands as ceilings for torchberries.
    if plant in HANGING_PLANTS and support == "tf_slice:root_strand":
        return True
    if support in SUPPORTED_BLOCKS or support == FIREFLY:
        return False
    return None


def collision_support(plant, collision, facing=None):
    """Require a full horizontal face touching the plant, including top slabs."""
    if not isinstance(collision, dict):
        return None
    try:
        lower = tuple(float(value) for value in collision["min"])
        upper = tuple(float(value) for value in collision["max"])
        if len(lower) != 3 or len(upper) != 3:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    if plant == FIREFLY:
        if facing not in FIREFLY_SUPPORT_OFFSETS:
            return None
        axis = 2 if facing in ("north", "south") else 0
        other_axis = 0 if axis == 2 else 2
        center_covered = all(lower[index] <= 0.5 <= upper[index] for index in (1, other_axis))
        if facing in ("north", "west"):
            return center_covered and lower[axis] <= 0 and upper[axis] > 0
        return center_covered and upper[axis] >= 1 and lower[axis] < 1
    full_width = lower[0] <= 0 and lower[2] <= 0 and upper[0] >= 1 and upper[2] >= 1
    if plant in HANGING_PLANTS:
        return full_width and lower[1] <= 0 and upper[1] > 0
    return full_width and upper[1] >= 1 and lower[1] < 1


def support_drop(plant, root_count=1):
    if plant == FIREFLY:
        return None
    if plant == "tf_slice:torchberry_plant_empty":
        return None
    item = plant
    count = 1
    if plant == "tf_slice:torchberry_plant":
        item = "tf_slice:torchberries"
    elif plant == "tf_slice:root_strand":
        item, count = "minecraft:stick", max(1, min(3, int(root_count)))
    elif plant.startswith("tf_slice:huge_lily_pad_"):
        # The four legacy pieces represent one item; only the NW piece drops it.
        if plant != "tf_slice:huge_lily_pad_nw":
            return None
        item = "tf_slice:huge_lily_pad"
    return {"newItemName": item, "newAuxValue": 0, "count": count}
