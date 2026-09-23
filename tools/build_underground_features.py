#!/usr/bin/env python3
"""Build Twilight Forest's deterministic underground feature layer.

NetEase disables every vanilla feature in the dimension, so these definitions
restore the upstream 4.3.2508 ore table explicitly instead of inheriting the
Overworld's version-dependent ore placements.
"""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
FEATURES = BP / "netease_features"
RULES = BP / "netease_feature_rules"
BIOMES = BP / "netease_biomes" / "dm33027004"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import biome_catalog


ORE_SPECS = {
    "coal": {
        "block": "minecraft:coal_ore",
        "vein_size": 16,
        "attempts": 20,
        "y_extent": [-32, 127],
    },
    "iron": {
        "block": "minecraft:iron_ore",
        "vein_size": 9,
        "attempts": 20,
        "y_extent": [-32, 63],
    },
    "gold": {
        "block": "minecraft:gold_ore",
        "vein_size": 9,
        "attempts": 2,
        "y_extent": [-32, 31],
    },
    "redstone": {
        "block": "minecraft:redstone_ore",
        "vein_size": 8,
        "attempts": 8,
        "y_extent": [-32, 15],
    },
    "diamond": {
        "block": "minecraft:diamond_ore",
        "vein_size": 8,
        "attempts": 1,
        "y_extent": [-32, 15],
    },
    "lapis": {
        "block": "minecraft:lapis_ore",
        "vein_size": 7,
        "attempts": 2,
        "y_extent": [-32, 30],
    },
    "copper": {
        "block": "minecraft:copper_ore",
        "vein_size": 10,
        "attempts": 6,
        "y_extent": [-32, 96],
    },
}

ROCK_CLUSTER_BLOCKS = {
    "andesite": "minecraft:andesite",
    "diorite": "minecraft:diorite",
    "granite": "minecraft:granite",
}

STONE_REPLACEABLES = [
    {"name": "minecraft:stone"},
    {"name": "minecraft:deepslate"},
]
ROOT_BIOME_TAG = "tf_slice_has_underground_roots"
CAVE_CEILING_BLOCKS = [
    "minecraft:dirt",
    "minecraft:coarse_dirt",
    "minecraft:moss_block",
    "minecraft:stone",
    "minecraft:deepslate",
    "tf_slice:root_block",
    "tf_slice:liveroot_block",
    "tf_slice:root_strand",
]
CAVE_PLANT_SPECS = {
    "root_strand": {
        "block": "tf_slice:root_strand",
        "origin_attempts": 4,
        "origin_y": 10,
        "scan_samples": 24,
        "scan_y": [-42, 0],
    },
    "torchberry_plant": {
        "block": "tf_slice:torchberry_plant",
        "origin_attempts": 8,
        "origin_y": 60,
        "scan_samples": 64,
        "scan_y": [-92, 0],
    },
    "hanging_roots": {
        "block": "minecraft:hanging_roots",
        "origin_attempts": 16,
        "origin_y": 0,
        "scan_samples": 32,
        "scan_y": [-32, 0],
    },
}


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def dimension_biome_filter(extra_tag=None):
    tests = [
        {
            "test": "has_biome_tag",
            "operator": "==",
            "value": "dm33027004",
        }
    ]
    if extra_tag:
        tests.append(
            {
                "test": "has_biome_tag",
                "operator": "==",
                "value": extra_tag,
            }
        )
    return [{"all_of": tests}]


def ore_feature_document(identifier, block, vein_size):
    return {
        "format_version": "1.16.0",
        "minecraft:ore_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "count": vein_size,
            "replace_rules": [
                {
                    "places_block": block,
                    "may_replace": list(STONE_REPLACEABLES),
                }
            ],
        },
    }


def underground_rule_document(
    identifier,
    feature,
    iterations,
    y,
    chance=None,
    extra_biome_tag=None,
):
    distribution = {
        "iterations": iterations,
        "coordinate_eval_order": "xzy",
        "x": {"distribution": "uniform", "extent": [0, 15]},
        "y": y,
        "z": {"distribution": "uniform", "extent": [0, 15]},
    }
    if chance is not None:
        distribution["scatter_chance"] = chance
    return {
        "format_version": "1.21.10",
        "minecraft:feature_rules": {
            "description": {
                "identifier": "tf_slice:%s" % identifier,
                "places_feature": "tf_slice:%s" % feature,
            },
            "conditions": {
                "placement_pass": "underground_pass",
                "minecraft:biome_filter": dimension_biome_filter(
                    extra_biome_tag
                ),
            },
            "distribution": distribution,
        },
    }


def rock_cluster_scatter_document(identifier, ore_feature):
    # The Java pipeline applies rarity before count: one chunk in ten receives
    # a burst of five attempts, rather than every attempt rolling separately.
    return {
        "format_version": "1.21.10",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_feature": "tf_slice:%s" % ore_feature,
            "project_input_to_floor": False,
            "distribution": {
                "iterations": 5,
                "coordinate_eval_order": "xzy",
                "x": {"distribution": "uniform", "extent": [0, 15]},
                "y": {"distribution": "triangle", "extent": [-64, 64]},
                "z": {"distribution": "uniform", "extent": [0, 15]},
            },
        },
    }


def cave_plant_single_document(identifier, block):
    return {
        "format_version": "1.21.40",
        "minecraft:single_block_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_block": [{"block": block, "weight": 1}],
            "enforce_placement_rules": False,
            "enforce_survivability_rules": False,
            # NetEase 3.9 does not register the Java/Bedrock cave_air alias
            # for deferred feature descriptors.  Underground air resolves
            # as minecraft:air in this runtime.
            "may_replace": ["minecraft:air"],
            "may_attach_to": {
                "auto_rotate": False,
                "min_sides_must_attach": 1,
                "top": list(CAVE_CEILING_BLOCKS),
            },
        },
    }


def cave_plant_scan_document(identifier, single_feature, spec):
    # The Java feature scans downward and wanders at most three blocks from
    # each origin. Sampling that same column volume is a bounded NetEase-safe
    # approximation that can find cave ceilings without runtime chunk edits.
    return {
        "format_version": "1.21.10",
        "minecraft:scatter_feature": {
            "description": {"identifier": "tf_slice:%s" % identifier},
            "places_feature": "tf_slice:%s" % single_feature,
            "project_input_to_floor": False,
            "distribution": {
                "iterations": spec["scan_samples"],
                "coordinate_eval_order": "xzy",
                "x": {"distribution": "triangle", "extent": [-3, 3]},
                "y": {
                    "distribution": "uniform",
                    "extent": spec["scan_y"],
                },
                "z": {"distribution": "triangle", "extent": [-3, 3]},
            },
        },
    }


def build_ore_features():
    for key, spec in ORE_SPECS.items():
        feature_name = "twilight_%s_ore_feature" % key
        write_json(
            FEATURES / (feature_name + ".json"),
            ore_feature_document(
                feature_name,
                spec["block"],
                spec["vein_size"],
            ),
        )
        write_json(
            RULES / (feature_name + "_rule.json"),
            underground_rule_document(
                feature_name + "_rule",
                feature_name,
                spec["attempts"],
                {
                    "distribution": "uniform",
                    "extent": spec["y_extent"],
                },
            ),
        )


def build_rock_clusters():
    for key, block in ROCK_CLUSTER_BLOCKS.items():
        ore_name = "twilight_%s_cluster_ore_feature" % key
        scatter_name = "twilight_%s_cluster_feature" % key
        write_json(
            FEATURES / (ore_name + ".json"),
            ore_feature_document(ore_name, block, 16),
        )
        write_json(
            FEATURES / (scatter_name + ".json"),
            rock_cluster_scatter_document(scatter_name, ore_name),
        )
        write_json(
            RULES / (scatter_name + "_rule.json"),
            underground_rule_document(
                scatter_name + "_rule",
                scatter_name,
                1,
                0,
                chance=10.0,
            ),
        )


def build_cave_plants():
    for key, spec in CAVE_PLANT_SPECS.items():
        single_name = "cave_%s_single_feature" % key
        scan_name = "cave_%s_scan_feature" % key
        write_json(
            FEATURES / (single_name + ".json"),
            cave_plant_single_document(single_name, spec["block"]),
        )
        write_json(
            FEATURES / (scan_name + ".json"),
            cave_plant_scan_document(scan_name, single_name, spec),
        )
        write_json(
            RULES / (scan_name + "_rule.json"),
            underground_rule_document(
                scan_name + "_rule",
                scan_name,
                spec["origin_attempts"],
                spec["origin_y"],
                extra_biome_tag=ROOT_BIOME_TAG,
            ),
        )
def update_root_biome_tags():
    root_biomes = set(biome_catalog.UNDERGROUND_ROOT_BIOMES)
    for entry in biome_catalog.BIOMES:
        path = BIOMES / (entry["identifier"] + ".json")
        document = json.loads(path.read_text(encoding="utf-8"))
        components = document["minecraft:biome"]["components"]
        if entry["identifier"] in root_biomes:
            components[ROOT_BIOME_TAG] = {}
        else:
            components.pop(ROOT_BIOME_TAG, None)
        write_json(path, document)


def build_root_rule():
    write_json(
        RULES / "wood_root_vein_feature_rule.json",
        underground_rule_document(
            "wood_root_vein_feature_rule",
            "wood_root_vein_feature",
            1,
            {"distribution": "uniform", "extent": [-32, 0]},
            chance=2.5,
            extra_biome_tag=ROOT_BIOME_TAG,
        ),
    )


def main():
    build_ore_features()
    build_rock_clusters()
    build_cave_plants()
    update_root_biome_tags()
    build_root_rule()
    print(
        "Generated %d ore placements, %d rock clusters, %d cave plants, "
        "and root biome tags."
        % (
            len(ORE_SPECS),
            len(ROCK_CLUSTER_BLOCKS),
            len(CAVE_PLANT_SPECS),
        )
    )


if __name__ == "__main__":
    main()
