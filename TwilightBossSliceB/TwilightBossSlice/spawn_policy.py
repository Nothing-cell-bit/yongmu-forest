# -*- coding: utf-8 -*-
"""Biome-aware natural-spawn policy for the Twilight dimension."""

import TwilightBossSlice.biome_catalog as biome_catalog
import TwilightBossSlice.leaf_decay_logic as leaf_decay_logic


DEFAULT_VANILLA_CREATURES = frozenset(
    ("minecraft:chicken", "minecraft:wolf")
)
# Lake and stream retain the default creature table on their available land.
# BASE_SOURCE_BIOMES also contains special swamps/dark forests; it is not a
# default-creature allowlist.
DEFAULT_CREATURE_BIOMES = frozenset(
    entry["identifier"]
    for entry in biome_catalog.BIOMES
    if entry["key"] not in (
        "spooky_forest", "swamp", "fire_swamp",
        "dark_forest", "dark_forest_center",
    )
)
SWAMP_BIOME = biome_catalog.BIOMES_BY_KEY["swamp"]["identifier"]
SPOOKY_BIOME = biome_catalog.BIOMES_BY_KEY["spooky_forest"]["identifier"]
DARK_FOREST_BIOME = biome_catalog.BIOMES_BY_KEY["dark_forest"]["identifier"]
DARK_FOREST_CENTER_BIOME = biome_catalog.BIOMES_BY_KEY[
    "dark_forest_center"
]["identifier"]

# Locked 4.3.2508 monster tables. Each biome has one script-owned pool;
# native inherited tables are cancelled to avoid missing entries and skewed
# vanilla/custom weights. Ambient bats remain engine-owned in Spooky Forest.
CONTROLLED_MONSTER_POOLS = {
    DARK_FOREST_BIOME: (
        ("minecraft:enderman", 2, 1, 2), ("minecraft:zombie", 5, 1, 2),
        ("minecraft:skeleton", 5, 1, 2), ("tf_slice:mist_wolf", 5, 1, 1),
        ("tf_slice:skeleton_druid", 5, 1, 1), ("tf_slice:king_spider", 1, 1, 1),
        ("tf_slice:kobold", 10, 1, 3), ("minecraft:witch", 2, 1, 1),
    ),
    SPOOKY_BIOME: (
        ("minecraft:spider", 50, 1, 2), ("minecraft:skeleton", 20, 1, 2),
        ("tf_slice:skeleton_druid", 5, 1, 1),
    ),
    SWAMP_BIOME: (
        ("minecraft:zombie", 10, 1, 2), ("tf_slice:mosquito_swarm", 10, 1, 1),
    ),
}
SPAWN_EMPTY_BLOCKS = frozenset(("minecraft:air", "minecraft:cave_air", "minecraft:void_air"))
SPAWN_FLUID_BLOCKS = frozenset(("minecraft:water", "minecraft:flowing_water", "minecraft:lava", "minecraft:flowing_lava"))


def is_leaf_support(block_name):
    name = leaf_decay_logic.canonical_leaf_name(block_name)
    return (leaf_decay_logic.is_connecting_leaf(name)
            or name in leaf_decay_logic.NON_CONNECTING_LEAVES)


def ground_support_allowed(block_name):
    name = str(block_name or "")
    return bool(name and name not in SPAWN_EMPTY_BLOCKS
                and name not in SPAWN_FLUID_BLOCKS and not is_leaf_support(name))


def should_cancel_twilight_spawn(
    args,
    twilight_dimension_id,
    twilight_namespace="tf_slice",
    biome_identifier=None,
):
    """Reject mobs outside the upstream biome-specific spawn tables."""
    try:
        dimension_id = int(args.get("dimensionId", 0))
    except (TypeError, ValueError):
        return False
    if dimension_id != int(twilight_dimension_id):
        return False

    declared_identifier = str(args.get("identifier", ""))
    declared_namespace = declared_identifier.split(":", 1)[0]
    # NetEase reports ModAPI-created mobs with the synthetic `custom`
    # namespace. Preserve that path for explicit tests and scripted spawns.
    if declared_namespace == "custom":
        return False

    real_identifier = str(
        args.get("realIdentifier") or declared_identifier
    )
    # The locked center biome uses an empty MobSpawnSettings.Builder. Keep
    # scripted ModAPI spawns above, but reject every natural table here,
    # including the dimension-wide tf_slice allowlist.
    if biome_identifier == DARK_FOREST_CENTER_BIOME:
        return True
    # Inherited native weights cannot be mixed with source monster weights.
    # Owned monster biomes use the explicit `custom` path and one source pool;
    # Spooky Forest's ambient bats keep their separate native category.
    if biome_identifier in CONTROLLED_MONSTER_POOLS:
        if biome_identifier == SPOOKY_BIOME and real_identifier == "minecraft:bat":
            return False
        return True
    if real_identifier.startswith("%s:" % str(twilight_namespace)):
        return False
    if (
        real_identifier in DEFAULT_VANILLA_CREATURES
        and biome_identifier in DEFAULT_CREATURE_BIOMES
    ):
        return False
    return True
