#!/usr/bin/env python3
"""Build the two dark-forest biomes and the catalog-driven dimension source."""

from __future__ import print_function

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog


PROFILES = {
    "dark_forest": {
        "sky": "#000000",
        "fog": "#000000",
        "water": "#3F76E4",
        "waterFog": "#050533",
        "grass": "#4B6754",
        "foliage": "#3B5E3F",
        "fogId": "tf_slice:fog_dark_forest",
        "extraTags": (
            "tf_slice_large_landmarks",
            "tf_slice_small_ruins",
            "tf_slice_dark_forest_groundcover",
            "tf_slice_dark_forest_ecology",
            "tf_slice_has_underground_roots",
        ),
    },
    "dark_forest_center": {
        "sky": "#000000",
        "fog": "#493000",
        "water": "#3F76E4",
        "waterFog": "#050533",
        # NetEase has no custom grass-color modifier. The source selects
        # 554114 for most temperature-noise samples and 667540 only below
        # -0.2, so use the dominant branch as the fixed approximation.
        "grass": "#554114",
        # FoliageColorHandler's normalized-noise comparison makes this the
        # effective 4.3.2508 runtime value (the declared override is bypassed).
        "foliage": "#E94E14",
        "fogId": "tf_slice:fog_dark_forest_center",
        "extraTags": (
            "tf_slice_large_landmarks",
            "tf_slice_dark_forest_groundcover",
            "tf_slice_dark_forest_center_no_natural_spawns",
            "tf_slice_has_underground_roots",
        ),
    },
}


def encoded(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(document), encoding="utf-8")


def server_biome(entry, profile):
    tags = {
        "dm33027004": {},
        "tf_slice_twilight_forest": {},
        "tf_slice_biome_%s" % entry["key"]: {},
    }
    for tag in profile["extraTags"]:
        tags[tag] = {}
    components = {
        "minecraft:climate": {
            "temperature": entry["temperature"],
            "downfall": entry["downfall"],
            "snow_accumulation": [0.0, 0.0],
        },
        "minecraft:overworld_height": {
            "noise_params": entry["noise_params"],
        },
        "minecraft:surface_parameters": {
            "sea_floor_depth": 7,
            "sea_floor_material": "minecraft:gravel",
            "foundation_material": "minecraft:stone",
            "mid_material": "minecraft:dirt",
            "top_material": "minecraft:grass",
            "sea_material": "minecraft:water",
        },
    }
    components.update(tags)
    return {
        "format_version": "1.14.0",
        "minecraft:biome": {
            "description": {
                "identifier": entry["identifier"],
                "inherits": entry["inherits"],
            },
            "components": components,
        },
    }


def client_biome(entry, profile):
    return {
        "format_version": "1.21.70",
        "minecraft:client_biome": {
            "description": {"identifier": entry["identifier"]},
            "components": {
                "minecraft:fog_appearance": {
                    "fog_identifier": profile["fogId"],
                },
                "minecraft:sky_color": {"sky_color": profile["sky"]},
                "minecraft:water_appearance": {
                    "surface_color": profile["water"],
                },
                "minecraft:foliage_appearance": {
                    "color": profile["foliage"],
                },
                "minecraft:grass_appearance": {"color": profile["grass"]},
            },
        },
    }


def fog(identifier, profile):
    return {
        "format_version": "1.16.100",
        "minecraft:fog_settings": {
            "description": {"identifier": profile["fogId"]},
            "distance": {
                "air": {
                    "fog_start": 0.18,
                    "fog_end": 0.72,
                    "fog_color": profile["fog"],
                    "render_distance_type": "render",
                },
                "water": {
                    "fog_start": 0.0,
                    "fog_end": 32.0,
                    "fog_color": profile["waterFog"],
                    "render_distance_type": "fixed",
                },
                "weather": {
                    "fog_start": 0.12,
                    "fog_end": 0.65,
                    "fog_color": profile["fog"],
                    "render_distance_type": "render",
                },
            },
        },
    }


def route_seed_stage_specs():
    """Return grouped companion/core seeds for active route content."""
    stages = []
    for profile in biome_catalog.ACTIVE_TERRITORY_CONTENT_PROFILES:
        route_key = profile["coreBiome"]
        profile_ids = tuple(
            instance["id"]
            for instance in biome_catalog.ACTIVE_TERRITORY_PROFILES
            if instance["sourceProfileId"] == profile["id"]
        )
        companion_geometry = dict(
            (
                variant,
                tuple(
                    box
                    for profile_id in profile_ids
                    for box in routes[profile_id]
                ),
            )
            for variant, routes in (
                biome_catalog.ROUTE_PROFILE_COMPANION_SEED_BOXES_BY_VARIANT.items()
            )
        )
        core_geometry = dict(
            (
                variant,
                tuple(routes[profile_id] for profile_id in profile_ids),
            )
            for variant, routes in (
                biome_catalog.ROUTE_PROFILE_CORE_SEED_BOXES_BY_VARIANT.items()
            )
        )
        stages.extend(
            (
                {
                    "profileId": profile["id"],
                    "profileIds": profile_ids,
                    "biomeKey": profile["companionBiome"],
                    "geometryByVariant": companion_geometry,
                },
                {
                    "profileId": profile["id"],
                    "profileIds": profile_ids,
                    "biomeKey": route_key,
                    "geometryByVariant": core_geometry,
                },
            )
        )
    return tuple(stages)


def route_stabilize_stage_specs():
    """Return grouped companion/core stabilize stages for active content."""
    stages = []
    for profile in biome_catalog.ACTIVE_TERRITORY_CONTENT_PROFILES:
        route_key = profile["coreBiome"]
        profile_ids = tuple(
            instance["id"]
            for instance in biome_catalog.ACTIVE_TERRITORY_PROFILES
            if instance["sourceProfileId"] == profile["id"]
        )
        companion_geometry = dict(
            (
                variant,
                tuple(routes[profile_id] for profile_id in profile_ids),
            )
            for variant, routes in (
                biome_catalog.ROUTE_PROFILE_STABLE_COMPANION_MASKS_BY_VARIANT.items()
            )
        )
        core_geometry = dict(
            (
                variant,
                tuple(routes[profile_id] for profile_id in profile_ids),
            )
            for variant, routes in (
                biome_catalog.ROUTE_PROFILE_STABLE_CORE_MASKS_BY_VARIANT.items()
            )
        )
        stages.extend(
            (
                {
                    "profileId": profile["id"],
                    "profileIds": profile_ids,
                    "biomeKey": profile["companionBiome"],
                    "routeKey": route_key,
                    "conditionBuilder": (
                        biome_catalog.route_biome_companion_stabilize_condition
                    ),
                    "geometryByVariant": companion_geometry,
                },
                {
                    "profileId": profile["id"],
                    "profileIds": profile_ids,
                    "biomeKey": route_key,
                    "routeKey": route_key,
                    "conditionBuilder": (
                        biome_catalog.route_biome_core_stabilize_condition
                    ),
                    "geometryByVariant": core_geometry,
                },
            )
        )
    return tuple(stages)


def dimension_document():
    source = [
        {
            "type": "random_with_weight",
            "pool": [
                {
                    "biome_type": entry["identifier"],
                    "weight": entry["weight"],
                }
                for entry in biome_catalog.RANDOM_SOURCE_BIOMES
            ],
        }
    ]
    # Preserve upstream's key -> cardinal companion -> zoom x2 -> stabilize ->
    # zoom x4 topology. The private first zoom belongs only to ordinary land so
    # its visible scale remains broad. All four upstream slots are occupied:
    # until Glacier and Final Highlands are ported, their stable profile IDs
    # borrow Fire Swamp and Dark Forest content. Geometry stays profile-keyed,
    # while identical content is grouped into the same low-resolution stages.
    source.extend(
        {"type": stage_type}
        for stage_type in biome_catalog.PRE_KEY_LAND_ZOOM_STAGES
    )
    for stage in route_seed_stage_specs():
        source.append(
            {
                "type": "condition",
                "condition": biome_catalog.route_biome_seed_condition(
                    stage["geometryByVariant"],
                ),
                "pool": [
                    biome_catalog.BIOMES_BY_KEY[stage["biomeKey"]]["identifier"]
                ],
            }
        )
    source.extend(
        {"type": stage_type}
        for stage_type in biome_catalog.ROUTE_PRE_STABILIZE_ZOOM_STAGES
    )
    for stage in route_stabilize_stage_specs():
        source.append(
            {
                "type": "condition",
                "condition": stage["conditionBuilder"](
                    stage["geometryByVariant"],
                    stage["routeKey"],
                ),
                "pool": [
                    biome_catalog.BIOMES_BY_KEY[stage["biomeKey"]]["identifier"]
                ],
            }
        )
    source.extend(
        {"type": stage_type}
        for stage_type in biome_catalog.FINAL_LAND_ZOOM_STAGES
    )
    stream = biome_catalog.BIOMES_BY_KEY["stream"]["identifier"]
    source.extend(
        {
            "type": "transition",
            "biome_a": first,
            "biome_b": second,
            "biome_transition": stream,
        }
        for first, second in biome_catalog.STREAM_TRANSITION_IDENTIFIER_PAIRS
    )
    return {
        "format_version": "1.14.0",
        "netease:dimension_info": {
            "components": {
                "netease:dimension_type": "minecraft:overworld",
                "netease:generator_noise": {},
                "netease:ban_vanilla_feature": {},
                "netease:ban_vanilla_structure": {},
                "netease:spawn_biomes": [
                    entry["identifier"]
                    for entry in biome_catalog.BASE_SOURCE_BIOMES
                ]
                + [biome_catalog.BIOMES_BY_KEY["lake"]["identifier"]],
                "netease:biome_source": source,
            }
        },
    }


def main():
    for key, profile in PROFILES.items():
        entry = biome_catalog.BIOMES_BY_KEY[key]
        write(
            BP / "netease_biomes" / "dm33027004" / (entry["identifier"] + ".json"),
            server_biome(entry, profile),
        )
        write(
            RP / "biomes" / (entry["identifier"] + ".client_biome.json"),
            client_biome(entry, profile),
        )
        write(RP / "fogs" / (key + ".fog.json"), fog(key, profile))
    write(BP / "netease_dimension" / "dm33027004.json", dimension_document())
    print("generated 2 dark-forest biomes, 2 fogs, and the dimension source")


if __name__ == "__main__":
    main()
