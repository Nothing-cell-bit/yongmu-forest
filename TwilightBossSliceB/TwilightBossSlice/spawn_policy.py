# -*- coding: utf-8 -*-
"""Biome-aware natural-spawn policy for the Twilight dimension."""

import TwilightBossSlice.biome_catalog as biome_catalog


DEFAULT_VANILLA_CREATURES = frozenset(
    ("minecraft:chicken", "minecraft:wolf")
)
SPOOKY_VANILLA_MOBS = frozenset(
    ("minecraft:bat", "minecraft:spider", "minecraft:skeleton")
)
SPOOKY_BIOME = biome_catalog.BIOMES_BY_KEY["spooky_forest"]["identifier"]
DARK_FOREST_BIOME = biome_catalog.BIOMES_BY_KEY["dark_forest"]["identifier"]
DARK_FOREST_CENTER_BIOME = biome_catalog.BIOMES_BY_KEY[
    "dark_forest_center"
]["identifier"]


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
    # NetEase's inherited monster rules use weights up to 100 while the
    # upstream Dark Forest table uses 1..10. Cancel the complete native table
    # here; StructureWorldgenService replaces it through the explicit `custom`
    # path above using the locked eight-entry source pool.
    if biome_identifier == DARK_FOREST_BIOME:
        return True
    if real_identifier.startswith("%s:" % str(twilight_namespace)):
        return False
    if (
        real_identifier in DEFAULT_VANILLA_CREATURES
        and biome_identifier in biome_catalog.ORDINARY_FOREST_BIOMES
    ):
        return False
    if (
        real_identifier in SPOOKY_VANILLA_MOBS
        and biome_identifier == SPOOKY_BIOME
    ):
        return False
    return True
