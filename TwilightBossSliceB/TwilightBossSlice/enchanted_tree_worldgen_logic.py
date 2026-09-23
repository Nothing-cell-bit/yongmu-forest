# -*- coding: utf-8 -*-
"""Pure placement policy for deferred Enchanted Forest profile trees."""

from TwilightBossSlice.mushroom_worldgen_logic import (
    is_canopy_replaceable,
    is_ground_support,
    is_surface_decoration,
    required_chunks,
    stable_seed,
)


ENCHANTED_BIOME = "dm33027004_birch_forest_mutated"
TRIGGER_STRUCTURES = {
    "regular_rainbow": "tf_slice:enchanted/tree_trigger/regular_rainbow",
    "vanilla_oak": "tf_slice:enchanted/tree_trigger/vanilla_oak",
    "vanilla_birch": "tf_slice:enchanted/tree_trigger/vanilla_birch",
    "large_rainbow": "tf_slice:enchanted/tree_trigger/large_rainbow",
}
TRIGGER_KINDS = dict(
    (structure_name, kind)
    for kind, structure_name in TRIGGER_STRUCTURES.items()
)
VARIANT_COUNTS = {
    "regular_rainbow": 16,
    "vanilla_oak": 1,
    "vanilla_birch": 1,
    "large_rainbow": 16,
}


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


def template_origin(root, center):
    return (
        int(root[0]) - int(center[0]),
        int(root[1]) - int(center[1]),
        int(root[2]) - int(center[2]),
    )
