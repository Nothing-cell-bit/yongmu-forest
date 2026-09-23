# -*- coding: utf-8 -*-
"""Pure placement policy for deferred Mushroom Forest canopy mushrooms."""


STRUCTURE_SIZE = (41, 40, 41)
CENTER = (20, 5, 20)
VARIANT_COUNTS = {"brown": 16, "red": 24}
TRIGGER_STRUCTURES = {
    "brown": "tf_slice:mushroom/canopy_trigger/brown",
    "red": "tf_slice:mushroom/canopy_trigger/red",
}
TRIGGER_KINDS = dict(
    (structure_name, kind)
    for kind, structure_name in TRIGGER_STRUCTURES.items()
)
MUSHROOM_BIOMES = frozenset(
    (
        "dm33027004_mushroom_island_shore",
        "dm33027004_mushroom_island",
    )
)
GROUND_SUPPORT_BLOCKS = frozenset(
    (
        "minecraft:grass",
        "minecraft:grass_block",
        "minecraft:dirt",
        "minecraft:coarse_dirt",
        "minecraft:podzol",
        "minecraft:mycelium",
        "minecraft:moss_block",
    )
)
CANOPY_REPLACEABLE_BLOCKS = frozenset(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "minecraft:vine",
        "minecraft:snow_layer",
        "minecraft:deadbush",
        "minecraft:brown_mushroom",
        "minecraft:red_mushroom",
        "minecraft:yellow_flower",
        "minecraft:red_flower",
        "tf_slice:mayapple",
        "tf_slice:fiddlehead",
        "tf_slice:mushgloom",
        "tf_slice:fallen_leaves",
        "tf_slice:firefly",
    )
)
SURFACE_DECORATION_BLOCKS = frozenset(
    tuple(CANOPY_REPLACEABLE_BLOCKS)
    + (
        "minecraft:mushroom_stem",
        "minecraft:brown_mushroom_block",
        "minecraft:red_mushroom_block",
        "minecraft:log",
        "minecraft:log2",
        "minecraft:oak_log",
        "minecraft:spruce_log",
        "minecraft:birch_log",
        "minecraft:jungle_log",
        "minecraft:acacia_log",
        "minecraft:dark_oak_log",
        "tf_slice:twilight_oak_log",
        "tf_slice:canopy_log",
        "tf_slice:rainbow_oak_log",
    )
)


def stable_seed(value):
    """Return a Python 2/3-stable FNV-1a value."""
    result = 2166136261
    for character in str(value):
        result ^= ord(character)
        result = (result * 16777619) & 0xFFFFFFFF
    if result >= 0x80000000:
        result -= 0x100000000
    return result


def template_origin(root):
    """Translate the real stem root to the 41x40x41 template origin."""
    return (
        int(root[0]) - CENTER[0],
        int(root[1]) - CENTER[1],
        int(root[2]) - CENTER[2],
    )


def required_chunks(origin, local_bounds):
    """List every world chunk touched by inclusive local bounds."""
    minimum_x = int(origin[0]) + int(local_bounds[0])
    minimum_z = int(origin[2]) + int(local_bounds[2])
    maximum_x = int(origin[0]) + int(local_bounds[3])
    maximum_z = int(origin[2]) + int(local_bounds[5])
    result = []
    for chunk_x in range(minimum_x >> 4, (maximum_x >> 4) + 1):
        for chunk_z in range(minimum_z >> 4, (maximum_z >> 4) + 1):
            result.append((chunk_x, chunk_z))
    return result


def is_ground_support(block_name):
    return str(block_name or "") in GROUND_SUPPORT_BLOCKS


def is_canopy_replaceable(block_name):
    block_name = str(block_name or "")
    if block_name in CANOPY_REPLACEABLE_BLOCKS:
        return True
    return block_name.endswith(
        (
            "_leaves",
            "_flower",
            "_sapling",
        )
    )


def is_surface_decoration(block_name):
    block_name = str(block_name or "")
    if block_name in SURFACE_DECORATION_BLOCKS:
        return True
    return block_name.endswith(
        (
            "_leaves",
            "_log",
            "_wood",
            "_sapling",
            "_flower",
            "_mushroom_block",
        )
    )


def variant_index(kind, world_seed, root_x, root_z):
    count = VARIANT_COUNTS[str(kind)]
    value = stable_seed(
        "%d:%d:%d:%s" % (
            int(world_seed),
            int(root_x),
            int(root_z),
            str(kind),
        )
    )
    return abs(value) % count


def candidate_key(kind, root_x, root_z):
    return "%s:%d,%d" % (str(kind), int(root_x), int(root_z))
